"""Original-interface API contract implemented independently for the ClaimsFlow workbench."""
import io, csv, json, os, time, zipfile
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from core import route_claim
from ai import CLAIM_FORM_FIELDS, analyze
from store import Store

router = APIRouter(prefix='/workbench')
ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get('CLAIMSFLOW_DATA_DIR', str(ROOT/'data')))
fresh = not (DATA_ROOT/'workbench_v7.json').exists()
storage = Store(DATA_ROOT/'workbench_v7.json')
SAMPLE_CASES = json.loads((ROOT/'sample_cases.json').read_text())
if fresh:
    storage.save({'claims':SAMPLE_CASES,'reviews':[]})
DOCROOT = DATA_ROOT/'evidence'
DOCROOT.mkdir(parents=True,exist_ok=True)
VALID_ROUTES = {'Fast-track', 'Standard Queue', 'Manual Review', 'Specialist Queue', 'Investigation Flag'}
ROUTES = {'Fast Track':'Fast-track','Investigation':'Investigation Flag'}
def translate(value):return ROUTES.get(value,value)
def now():return datetime.now(timezone.utc).isoformat()
def case_of(item):
    return {'id':item['id'],'title':item.get('title',item.get('description','Synthetic claim')),'status':item.get('status','New'),'documents':item.get('documents',[]),'reference':item.get('reference',{})}
def get_case(data,ident):
    found=next((x for x in data['claims'] if x['id']==ident),None)
    if not found:raise HTTPException(404,'Claim not found')
    return found
def attempts(data):return data.get('reviews',[])
def ensure_fields(d):
    return {'policyNumber':d.get('policy_number',''),'claimant':d.get('claimant',''),'claimType':d.get('claim_type',''),'estimatedDamage':str(d.get('estimated_damage','')),'description':d.get('description','')}
def field_key(name):
    return ''.join(character.lower() for character in name if character.isalnum())


FORM_FIELD_BY_KEY = {field_key(name): name for name in CLAIM_FORM_FIELDS}


def extracted_form_fields(fields):
    extracted = {}
    for name, value in fields.items():
        field = FORM_FIELD_BY_KEY.get(field_key(name))
        text = '' if value is None else str(value).strip()
        if field and text and (field not in extracted or name == field):
            extracted[field] = text
    return extracted


def new_claim(data,title,documents):
    ident=f'CLM-{max([int(x["id"].split("-")[-1]) for x in data["claims"] if x["id"].split("-")[-1].isdigit()] or [0])+1:04d}'
    item={'id':ident,'title':title,'description':title,'claim_type':'Motor','claimant':'Synthetic claimant','policy_number':'','estimated_damage':0,'status':'New','documents':documents,'reference':{}}
    data['claims'].append(item)
    return item
@router.get('/cases')
def cases():return [case_of(x) for x in storage.read()['claims']]
@router.get('/attempts')
def list_attempts():return attempts(storage.read())
@router.get('/cases/{case_id}')
def case_detail(case_id:str):
    return case_of(get_case(storage.read(),case_id))
@router.get('/cases/{case_id}/history')
def history(case_id:str):
    data=storage.read();return {'case':case_of(get_case(data,case_id)),'attempts':[x for x in attempts(data) if x['caseId']==case_id]}
@router.get('/cases/{case_id}/reports/{review_id}.pdf')
def pdf_report(case_id: str, review_id: str):
    """Download a PDF of a saved, human-reviewed synthetic claim."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from reportlab.lib.utils import simpleSplit
    from xml.sax.saxutils import escape
    data = storage.read()
    claim = get_case(data, case_id)
    review = next((r for r in attempts(data) if r.get('id') == review_id and r.get('caseId') == case_id), None)
    if review is None:
        raise HTTPException(404, 'Saved review not found')
    def safe(value):
        return escape(str(value if value is not None else ''))
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=(595,842), rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    story = [Paragraph('ClaimsFlow | Synthetic Claim Report', styles['Title']), Spacer(1,14),
        Paragraph(f"<b>Claim:</b> {safe(case_id)} - {safe(claim.get('title',''))}", styles['Normal']),
        Paragraph(f"<b>Saved review:</b> {safe(review_id)}", styles['Normal']),
        Paragraph(f"<b>Submitted:</b> {safe(review.get('submittedAt',''))}", styles['Normal']),
        Paragraph(f"<b>Review method:</b> {safe(review.get('mode',''))}", styles['Normal']),
        Spacer(1,14), Paragraph('Human decision', styles['Heading2']),
        Paragraph(f"<b>Final route:</b> {safe(review.get('finalRoute',''))}", styles['Normal']),
        Paragraph(f"<b>Reason:</b> {safe(review.get('decisionReason','Not recorded'))}", styles['Normal']),
        Spacer(1,12), Paragraph('Reviewed claim details', styles['Heading2'])]
    for key, value in (review.get('fields') or {}).items():
        story.append(Paragraph(f"<b>{safe(key)}:</b> {safe(value)}", styles['Normal']))
        story.append(Spacer(1,4))
    story += [Spacer(1,12), Paragraph('Supporting evidence (filenames)', styles['Heading2'])]
    for filename in claim.get('documents',[]):
        story.append(Paragraph(safe(filename), styles['Normal']))
    if review.get('aiRecommendedRoute'):
        story += [Spacer(1,12), Paragraph('AI-assisted analysis', styles['Heading2']),
            Paragraph(f"<b>AI suggested route:</b> {safe(review['aiRecommendedRoute'])}", styles['Normal'])]
    story += [Spacer(1,18), Paragraph('Prototype using synthetic data. AI suggestions require human verification. Original PDFs are not embedded in this report.', styles['Italic'])]
    document.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="ClaimsFlow_{case_id}_{review_id[:8]}.pdf"', 'Cache-Control':'no-store'})

@router.post('/cases/{case_id}/ai-process')
def ai_process(case_id:str):
    data=storage.read();item=get_case(data,case_id)
    result=analyze(item)
    provider = result['provider']
    extracted = extracted_form_fields(result['fields']) if provider == 'gemini' else {}
    return {
        'id': str(uuid4()),
        'fields': {**ensure_fields(item), **extracted},
        'extractedFields': extracted,
        'recommendedRoute': translate(result['route']),
        'reasoning': result['reason'],
        'provider': provider,
        'warning': result.get('warning'),
        'apiSeconds': result['elapsed_seconds'],
        'extractionStatus': {'method': provider},
        'routingStatus': {'method': provider},
    }

class Review(BaseModel):
    caseId: str
    mode: str
    elapsedSeconds: float = Field(ge=0)
    fields: dict
    finalRoute: str
    decisionReason: str = ''
    aiAttemptId: str | None = None
    aiExtractedFields: dict[str, str] | None = None
@router.post('/attempts')
def save_attempt(value:Review):
    if value.mode not in ('manual','ai') or value.finalRoute not in VALID_ROUTES:raise HTTPException(422,'Invalid mode or route')
    if value.mode=='ai' and not value.aiAttemptId:raise HTTPException(422,'Run AI before submitting')
    def update(data):
        item=get_case(data,value.caseId)
        rec={'id':str(uuid4()),**value.model_dump(exclude={'aiExtractedFields'}),'submittedAt':now(),'quality':{'referenceAvailable':False,'fieldAccuracy':None,'routeAgreement':None},'isRevision':False}
        if value.mode == 'ai' and value.aiExtractedFields:
            rec['aiExtractedFields'] = extracted_form_fields(value.aiExtractedFields)
        data.setdefault('reviews',[]).append(rec);item['status']='Reviewed';return rec
    return storage.update(update)
class Revision(BaseModel):
    basedOnAttemptId:str;fields:dict;finalRoute:str;decisionReason:str
@router.post('/cases/{case_id}/revisions')
def revision(case_id:str,value:Revision):
    if value.finalRoute not in VALID_ROUTES:raise HTTPException(422,'Invalid route')
    def update(data):
        get_case(data,case_id)
        original=next((x for x in attempts(data) if x['id']==value.basedOnAttemptId and x['caseId']==case_id),None)
        if not original:raise HTTPException(404,'Original review not found')
        rec={**original,'id':str(uuid4()),'fields':value.fields,'finalRoute':value.finalRoute,'decisionReason':value.decisionReason,'submittedAt':now(),'isRevision':True}
        data['reviews'].append(rec);return rec
    return storage.update(update)
async def validate_pdfs(documents):
    if not 1<=len(documents)<=8:raise HTTPException(422,'Upload 1 to 8 PDFs')
    validated=[]
    for idx,upload in enumerate(documents):
        blob=await upload.read(8*1024*1024+1)
        if len(blob)>8*1024*1024 or not blob.startswith(b'%PDF-'):raise HTTPException(422,'Each document must be a PDF smaller than 8 MB')
        name=f'{uuid4().hex}_{Path(upload.filename or "evidence.pdf").name}'
        name=name.replace('/','_').replace('\\','_')
        validated.append((name,blob))
    return validated

def write_pdfs(case_id,validated):
    target=DOCROOT/case_id;target.mkdir(parents=True,exist_ok=True)
    for name,blob in validated:
        (target/name).write_bytes(blob)
    return [name for name,_ in validated]
@router.post('/cases')
async def upload_case(title:str=Form(...),documents:list[UploadFile]=File(...)):
    if not title.strip():raise HTTPException(422,'Title required')
    validated=await validate_pdfs(documents)
    item=storage.update(lambda d:new_claim(d,title.strip(),[]))
    names=write_pdfs(item['id'],validated)
    def update(data):
        found=get_case(data,item['id']);found['documents']=names;return case_of(found)
    return storage.update(update)
@router.post('/cases/{case_id}/documents')
async def add_documents(case_id:str,documents:list[UploadFile]=File(...)):
    get_case(storage.read(),case_id)
    names=write_pdfs(case_id,await validate_pdfs(documents))
    def update(data):
        item=get_case(data,case_id);item['documents'].extend(names);return case_of(item)
    return storage.update(update)
@router.get('/cases/{case_id}/documents/{filename}')
def document(case_id:str,filename:str):
    item=get_case(storage.read(),case_id)
    if filename not in item['documents']:raise HTTPException(404,'Document not found')
    target=DOCROOT/case_id/filename
    if not target.is_file():raise HTTPException(404,'PDF file is missing')
    return FileResponse(target,media_type='application/pdf')
@router.post('/cases/bulk-import')
async def bulk_import(archive:UploadFile=File(...)):
    raw=await archive.read(100*1024*1024+1)
    if len(raw)>100*1024*1024:raise HTTPException(422,'Archive exceeds 100 MB')
    try:zf=zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:raise HTTPException(422,'Invalid ZIP archive')
    with zf:
        members=[x for x in zf.infolist() if not x.is_dir()]
        groups={}
        if len(members)>800 or sum(e.file_size for e in members)>100*1024*1024:
            raise HTTPException(422,'Expanded archive exceeds 100 MB or 800 files')
        for entry in members:
            parts=Path(entry.filename).parts
            if '..' in parts or entry.file_size>8*1024*1024:raise HTTPException(422,'Unsafe or oversized ZIP member')
            if len(parts)==2 and parts[-1].lower().endswith('.pdf'):
                groups.setdefault(parts[0],[]).append((parts[-1],zf.read(entry)))
        if len(groups)>100:raise HTTPException(422,'Maximum 100 claims')
        for group,docs in groups.items():
            if not 1<=len(docs)<=8 or any(not b.startswith(b'%PDF-') for _,b in docs):raise HTTPException(422,'Invalid PDF group')
        for group,docs in groups.items():
            item=storage.update(lambda d:new_claim(d,group,[]))
            target=DOCROOT/item['id'];target.mkdir(parents=True,exist_ok=True)
            names=[]
            for i,(name,blob) in enumerate(docs):
                safe=f'{i+1}_{Path(name).name}';(target/safe).write_bytes(blob);names.append(safe)
            storage.update(lambda d:get_case(d,item['id'])['documents'].extend(names))
        return {'imported':len(groups)}
@router.post('/reset')
def reset():
    storage.save({'claims':SAMPLE_CASES,'reviews':[]})
    return {'ok':True}
@router.get('/evaluation/runs')
def eval_runs():return storage.read().get('evaluations',[])
class Evaluation(BaseModel):
    caseIds:list[str];manualMinutes:float=10;verificationMinutes:float=3;hourlyRate:float=25;apiCost:float=.02;simulateHuman:bool=True;humanErrorRate:float=.05;humanRoutingErrorRate:float=.05;documentMinutes:float=1.5;complexityMinutes:float=2
@router.post('/evaluation/run')
def evaluation(payload:Evaluation):
    data=storage.read();chosen=[get_case(data,i) for i in payload.caseIds]
    cases=[]
    for item in chosen:
        result=analyze(item)
        success=result['provider']=='gemini'
        cases.append({'caseId':item['id'],'status':'ok' if success else 'fallback','apiSeconds':result['elapsed_seconds'],'recommendedRoute':translate(result['route']),'fields':result.get('fields',{}),'humanSimulation':{'cost':payload.manualMinutes*payload.hourlyRate/60} if payload.simulateHuman else None,'warning':result.get('warning')})
    good=[c for c in cases if c['status']=='ok']
    run={'id':str(uuid4()),'createdAt':now(),'settings':payload.model_dump(),'cases':cases,'summary':{'totalCases':len(cases),'geminiSuccesses':len(good),'fallbacks':len(cases)-len(good),'errors':0,'simulatedHumanMinutes':payload.manualMinutes if payload.simulateHuman else None,'simulatedHumanCost':payload.manualMinutes*payload.hourlyRate/60 if payload.simulateHuman else None,'fieldAccuracy':None,'routingAgreement':None,'simulatedHumanFieldAccuracy':(1-payload.humanErrorRate)*100 if payload.simulateHuman else None,'simulatedHumanRoutingAgreement':(1-payload.humanRoutingErrorRate)*100 if payload.simulateHuman else None}}
    def update(d):d.setdefault('evaluations',[]).insert(0,run);return run
    return storage.update(update)
