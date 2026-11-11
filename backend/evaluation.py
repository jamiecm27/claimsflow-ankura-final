"""Automated synthetic-case evaluation; never creates human-approved attempts."""
import json
import time
import hashlib
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import workbench as wb
from extractor import extract_fields
from llm_extractor import extract_fields_with_gemini, route_claim_with_gemini, get_gemini_model
from validator import find_missing_fields
from router import route_claim

router = APIRouter(prefix='/workbench/evaluation', tags=['evaluation'])

class Settings(BaseModel):
    manualMinutes: float = Field(default=10, ge=0, le=120)
    verificationMinutes: float = Field(default=3, ge=0, le=120)
    hourlyRate: float = Field(default=25, ge=0, le=1000)
    apiCost: float = Field(default=0.02, ge=0, le=100)
    caseIds: list[str] | None = None
    simulateHuman: bool = True
    humanErrorRate: float = Field(default=0.05, ge=0, le=0.5)
    humanRoutingErrorRate: float = Field(default=0.05, ge=0, le=0.5)
    documentMinutes: float = Field(default=1.5, ge=0, le=60)
    complexityMinutes: float = Field(default=2.0, ge=0, le=60)

def normalized(v):
    return ' '.join(str(v or '').casefold().split())

def analyze(text):
    started = time.perf_counter()
    fallback_fields = extract_fields(text)
    fields, extraction = extract_fields_with_gemini(text, fallback_fields)
    missing = find_missing_fields(fields)
    default = route_claim(fields, missing)
    route, routing = route_claim_with_gemini(text, fields, missing, default)
    return {'fields': fields, 'route': route['route'], 'extraction': extraction.get('method'), 'routing': routing.get('method'), 'seconds': round(time.perf_counter()-started,3)}

@router.get('/runs')
def runs():
    with wb.LOCK:
        return list(reversed(wb.read_db().get('evaluationRuns', [])))[:12]

@router.post('/run')
def run(settings: Settings):
    with wb.LOCK:
        db = wb.read_db()
        cases = [c for c in db['cases'] if settings.caseIds is None or c['id'] in settings.caseIds]
    if not cases:
        raise HTTPException(400, 'No claims selected')
    if len(cases) > 100:
        raise HTTPException(400, 'Select at most 100 claims per run')
    outcomes=[]
    for case in cases:
        reference = wb.rubric(case['id'])
        item={'caseId':case['id'], 'documents':len(case['documents']), 'expectedRoute':reference['expectedRoute'] if reference else None}
        try:
            text=wb.case_text(case)
            result=analyze(text)
            expected=reference['fields'] if reference else {}
            matched=sum(normalized(result['fields'].get(k))==normalized(v) for k,v in expected.items())
            item.update({'status':'ok' if result['extraction']=='gemini' and result['routing']=='gemini' else 'fallback',
                         'extractionMethod':result['extraction'],'routingMethod':result['routing'],
                         'fieldAccuracy':round(100*matched/len(expected),1) if expected else None,
                         'correctFields':matched,'scoredFields':len(expected),
                         'recommendedRoute':result['route'],'routeAgreement':result['route']==reference['expectedRoute'] if reference else None,
                         'apiSeconds':result['seconds']})
        except Exception as exc:
            item.update({'status':'error','error':str(exc)[:250]})
        outcomes.append(item)
    # Deterministic synthetic human baseline. It is NOT a measured human outcome.
    # Use a stable hash to avoid random-looking changes on every refresh.
    if settings.simulateHuman:
        for case, item in zip(cases, outcomes):
            ref=wb.rubric(case['id'])
            complexity = 1.0 + (0.35 if len(case['documents']) > 2 else 0)
            estimated_minutes = round((settings.manualMinutes + len(case['documents'])*settings.documentMinutes + settings.complexityMinutes)*complexity,2)
            def draw(salt):
                digest=hashlib.sha256((case['id']+salt).encode()).hexdigest()
                return int(digest[:12],16)/float(16**12)
            if ref:
                keys=list(ref['fields'])
                correct=sum(draw('field:'+k)>=settings.humanErrorRate for k in keys)
                route_match=draw('route')>=settings.humanRoutingErrorRate
                # Only report agreement, not fabricated human-entered field values.
                item['humanSimulation']={'minutes':estimated_minutes, 'cost':round(estimated_minutes*settings.hourlyRate/60,2),
                    'fieldAccuracy':round(100*correct/len(keys),1) if keys else None,
                    'routeAgreement':route_match, 'benchmarkAvailable':True}
            else:
                item['humanSimulation']={'minutes':estimated_minutes, 'cost':round(estimated_minutes*settings.hourlyRate/60,2),
                    'fieldAccuracy':None,'routeAgreement':None,'benchmarkAvailable':False}
    valid=[x for x in outcomes if x['status']=='ok']
    scored=sum(x['scoredFields'] for x in valid)
    scored_routes=[x for x in valid if x['routeAgreement'] is not None]
    api_time=sum(x['apiSeconds'] for x in valid)
    n=len(valid)
    savings_per_case=(settings.manualMinutes-settings.verificationMinutes)*settings.hourlyRate/60-settings.apiCost
    simulated=[x['humanSimulation'] for x in outcomes if 'humanSimulation' in x]
    simulated_scored=[x for x in simulated if x['benchmarkAvailable']]
    summary={'totalCases':len(outcomes),'geminiSuccesses':n,'fallbacks':sum(x['status']=='fallback' for x in outcomes),
             'errors':sum(x['status']=='error' for x in outcomes),
             'fieldAccuracy':round(100*sum(x['correctFields'] for x in valid)/scored,1) if scored else None,
             'routingAgreement':round(100*sum(x['routeAgreement'] for x in scored_routes)/len(scored_routes),1) if scored_routes else None,
             'routingScored':len(scored_routes),
             'meanApiSeconds':round(api_time/n,2) if n else None,
             'modelledSavingPerClaim':round(savings_per_case,2),
             'simulatedHumanMinutes':round(sum(x['minutes'] for x in simulated)/len(simulated),2) if simulated else None,
             'simulatedHumanCost':round(sum(x['cost'] for x in simulated)/len(simulated),2) if simulated else None,
             'simulatedHumanFieldAccuracy':round(sum(x['fieldAccuracy'] for x in simulated_scored)/len(simulated_scored),1) if simulated_scored else None,
             'simulatedHumanRoutingAgreement':round(100*sum(x['routeAgreement'] for x in simulated_scored)/len(simulated_scored),1) if simulated_scored else None}
    report={'id':uuid4().hex,'createdAt':wb.now(),'model':get_gemini_model(),
            'settings':settings.model_dump(), 'summary':summary,'cases':outcomes,
            'notes':['Only full Gemini extraction and routing successes count towards AI accuracy metrics.',
                     'Reference answers are provisional synthetic benchmarks, not independently adjudicated ground truth.',
                     'Simulated human handling time, field error rate and routing error rate are assumptions, not observed staff performance.',
                     'Human simulation is deterministic and does not call Gemini or create claim decisions.',
                     'Evaluation runs do not alter operational claim status.']}
    with wb.LOCK:
        db=wb.read_db();db.setdefault('evaluationRuns',[]).append(report);wb.write_db(db)
    return report
