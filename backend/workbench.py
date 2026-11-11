"""Synthetic workbench cases and timed manual/AI attempts."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from extractor import extract_text_from_pdf, extract_fields
from llm_extractor import extract_fields_with_gemini, route_claim_with_gemini
from validator import find_missing_fields
from router import route_claim

router = APIRouter(prefix='/workbench', tags=['workbench'])
BASE = Path(__file__).resolve().parent
SAMPLES = BASE / 'sample-docs'
DB = BASE / 'data' / 'workbench.json'
REFERENCE = BASE / 'data' / 'reference_answers.json'
MAX_DOCS = 8
MAX_BYTES = 8 * 1024 * 1024
LOCK = Lock()
ROUTES = {'Fast-track', 'Manual Review', 'Investigation Flag', 'Specialist Queue', 'Standard Queue'}

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def initial():
    names = sorted(SAMPLES.glob('FNOL_sample_*.pdf'))
    return {'cases': [{'id': f'CLM-{i:03d}', 'title': name.stem.replace('FNOL_sample_', '').replace('_clean', '').replace('_', ' ').title(), 'documents': [name.name, f'CLM_{i:03d}_supporting_evidence.pdf'], 'status': 'New', 'createdAt': now()} for i, name in enumerate(names, 1)], 'attempts': []}

def read_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    if not DB.exists():
        write_db(initial())
    return json.loads(DB.read_text(encoding='utf-8'))

def write_db(data):
    DB.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, DB)

def get_case(data, case_id):
    case = next((c for c in data['cases'] if c['id'] == case_id), None)
    if not case:
        raise HTTPException(404, 'Claim not found')
    return case

def case_text(case):
    parts = []
    for filename in case['documents']:
        path = evidence_path(case, filename)
        if not path.is_file():
            raise HTTPException(404, 'Evidence document not found')
        parts.append(f'--- Evidence: {path.name} ---\n{extract_text_from_pdf(path)}')
    return '\n\n'.join(parts)


def evidence_path(case, filename):
    if filename not in case['documents'] or Path(filename).name != filename:
        raise HTTPException(404, 'Evidence not part of this claim')
    path = (BASE / 'uploads' / case['id'] / filename) if filename.startswith('evidence_') else SAMPLES / filename
    if not path.is_file():
        raise HTTPException(404, 'Evidence document not found')
    return path

def rubric(case_id):
    if not REFERENCE.exists():
        return None
    return json.loads(REFERENCE.read_text()).get(case_id)

def score(fields, final_route, case_id):
    reference = rubric(case_id)
    if not reference:
        return {'referenceAvailable': False, 'fieldAccuracy': None, 'routeAgreement': None}
    expected = reference['fields']
    keys = list(expected)
    correct = sum(' '.join(str(fields.get(k) or '').lower().split()) == ' '.join(str(expected[k]).lower().split()) for k in keys)
    return {'referenceAvailable': True, 'fieldAccuracy': round(100*correct/len(keys),1) if keys else None, 'correctFields': correct, 'scoredFields': len(keys), 'routeAgreement': final_route == reference['expectedRoute'], 'expectedRoute': reference['expectedRoute']}

@router.post('/cases')
async def create_case(title: str = Form(...), documents: list[UploadFile] = File(...)):
    if not title.strip() or len(title)>150 or not (1 <= len(documents) <= MAX_DOCS):
        raise HTTPException(400, 'Provide a title and 1-8 PDF evidence documents')
    case_id = 'CLM-' + uuid4().hex[:8].upper()
    saved=[]
    folder=BASE/'uploads'/case_id
    folder.mkdir(parents=True,exist_ok=True)
    try:
        for i, doc in enumerate(documents,1):
            if not (doc.filename or '').lower().endswith('.pdf'):
                raise HTTPException(400,'PDF evidence only')
            contents=await doc.read(MAX_BYTES+1)
            if len(contents)>MAX_BYTES or not contents.startswith(b'%PDF'):
                raise HTTPException(400,'Invalid PDF or file exceeds 8 MB')
            name=f'evidence_{i:02d}.pdf'
            path=folder/name
            path.write_bytes(contents)
            try:
                extract_text_from_pdf(path)
            except Exception:
                raise HTTPException(400,'PDF could not be read')
            saved.append(name)
    except Exception:
        import shutil
        shutil.rmtree(folder,ignore_errors=True)
        raise
    case={'id':case_id,'title':title.strip(),'documents':saved,'documentLabels':{name:(doc.filename or name) for name,doc in zip(saved,documents)},'status':'New','createdAt':now(),'synthetic':True}
    with LOCK:
        data=read_db();data['cases'].append(case);write_db(data)
    return case

@router.post('/cases/bulk-import')
async def bulk_import_claims(archive: UploadFile = File(...)):
    """Import fictional claim folders from a ZIP; optional manifest.csv with folder,title columns."""
    import csv
    import io
    import shutil
    import zipfile
    if not (archive.filename or '').lower().endswith('.zip'):
        raise HTTPException(400, 'Choose a ZIP archive')
    payload = await archive.read(100 * 1024 * 1024 + 1)
    if len(payload) > 100 * 1024 * 1024:
        raise HTTPException(400, 'ZIP must be 100 MB or smaller')
    try:
        z = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile:
        raise HTTPException(400, 'Invalid ZIP archive')
    with z:
        entries = [i for i in z.infolist() if not i.is_dir()]
        if len(entries) > 1000 or sum(i.file_size for i in entries) > 150 * 1024 * 1024:
            raise HTTPException(400, 'Too many files or too much uncompressed data')
        if any(i.filename.startswith('/') or '..' in Path(i.filename).parts or '\\' in i.filename for i in entries):
            raise HTTPException(400, 'Unsafe ZIP entry name')
        manifests = [i for i in entries if i.filename == 'manifest.csv']
        titles = {}
        if manifests:
            try:
                for row in csv.DictReader(io.StringIO(z.read(manifests[0]).decode('utf-8-sig'))):
                    folder = (row.get('folder') or '').strip().strip('/')
                    title = (row.get('title') or '').strip()
                    if not folder or '/' in folder or not title or len(title)>150 or folder in titles:
                        raise ValueError('Invalid or duplicate manifest entry')
                    titles[folder] = title
            except (ValueError, UnicodeError) as e:
                raise HTTPException(400, f'Invalid manifest.csv: {e}')
        groups = {}
        for i in entries:
            if i.filename == 'manifest.csv' or i.filename.startswith('__MACOSX/') or i.filename.endswith('.DS_Store'):
                continue
            parts = i.filename.split('/')
            if len(parts) != 2 or not parts[1].lower().endswith('.pdf'):
                raise HTTPException(400, 'Use one folder per claim containing only PDFs, plus optional manifest.csv')
            groups.setdefault(parts[0], []).append(i)
        if not groups or len(groups)>100:
            raise HTTPException(400, 'ZIP must contain 1–100 claim folders')
        if titles and set(titles) != set(groups):
            raise HTTPException(400, 'Manifest folders must match claim folders')
        for folder, docs in groups.items():
            if not (1 <= len(docs) <= MAX_DOCS):
                raise HTTPException(400, f'{folder}: each claim needs 1–8 PDFs')
            for doc in docs:
                if doc.file_size > MAX_BYTES or doc.compress_size == 0 or doc.file_size > max(doc.compress_size * 100, 1024*1024):
                    raise HTTPException(400, f'{folder}: PDF too large or suspicious compression')
        created = []
        folders = []
        try:
            for folder, docs in sorted(groups.items()):
                case_id = 'CLM-' + uuid4().hex[:8].upper()
                dest = BASE / 'uploads' / case_id
                dest.mkdir(parents=True, exist_ok=False)
                folders.append(dest)
                names, labels = [], {}
                for n, doc in enumerate(sorted(docs,key=lambda d:d.filename),1):
                    content = z.read(doc)
                    if not content.startswith(b'%PDF'):
                        raise ValueError(f'{folder}: invalid PDF')
                    name = f'evidence_{n:02d}.pdf'
                    path = dest / name
                    path.write_bytes(content)
                    extract_text_from_pdf(path)
                    names.append(name)
                    labels[name] = Path(doc.filename).name
                created.append({'id':case_id,'title':titles.get(folder, folder.replace('_',' '))[:150], 'documents':names, 'documentLabels':labels,'status':'New','createdAt':now(),'synthetic':True})
            with LOCK:
                data=read_db()
                data['cases'].extend(created)
                write_db(data)
        except Exception as e:
            for dest in folders:
                shutil.rmtree(dest, ignore_errors=True)
            raise HTTPException(400, f'Import cancelled; no claims added: {e}')
        return {'imported':len(created),'cases':created}

@router.post('/cases/{case_id}/documents')
async def add_documents(case_id: str, documents: list[UploadFile] = File(...)):
    with LOCK:
        case=get_case(read_db(),case_id)
        old_count=len(case['documents'])
    if not documents or old_count+len(documents)>MAX_DOCS:
        raise HTTPException(400,'Maximum 8 PDFs per claim')
    folder=BASE/'uploads'/case_id
    folder.mkdir(parents=True,exist_ok=True)
    pending=[]
    try:
        for i,doc in enumerate(documents,old_count+1):
            if not (doc.filename or '').lower().endswith('.pdf'):
                raise HTTPException(400,'PDF evidence only')
            contents=await doc.read(MAX_BYTES+1)
            if len(contents)>MAX_BYTES or not contents.startswith(b'%PDF'):
                raise HTTPException(400,'Invalid PDF or file exceeds 8 MB')
            name=f'evidence_{i:02d}_{uuid4().hex[:6]}.pdf'
            path=folder/name;path.write_bytes(contents)
            try:extract_text_from_pdf(path)
            except Exception:raise HTTPException(400,'PDF could not be read')
            pending.append((name,doc.filename or name))
    except Exception:
        for name,_ in pending:(folder/name).unlink(missing_ok=True)
        raise
    with LOCK:
        data=read_db();case=get_case(data,case_id)
        case['documents'].extend(name for name,_ in pending)
        case.setdefault('documentLabels',{}).update(dict(pending))
        write_db(data)
    return case

@router.get('/cases/{case_id}/history')
def case_history(case_id: str):
    with LOCK:
        data=read_db();case=get_case(data,case_id)
        return {'case':case,'attempts':[a for a in data['attempts'] if a['caseId']==case_id], 'aiRuns':[{'id':r['id'],'processedAt':r['processedAt'],'recommendedRoute':r['recommendedRoute'],'extractionStatus':r['extractionStatus'],'routingStatus':r['routingStatus']} for r in data.get('aiRuns',[]) if r['caseId']==case_id]}

@router.get('/evaluation/reference-summary')
def reference_summary():
    references=json.loads(REFERENCE.read_text()) if REFERENCE.exists() else {}
    return {'syntheticReferenceCases':len(references),'method':'Exact normalized field comparison against synthetic baseline; routing agreement against manually specified expected queue. Not independent clinical or insurance adjudication.'}

class Submission(BaseModel):
    caseId: str
    mode: str
    elapsedSeconds: float = Field(ge=0, le=86400)
    fields: dict = Field(default_factory=dict)
    finalRoute: str
    decisionReason: str = ''
    aiAttemptId: str | None = None

@router.get('/cases')
def list_cases():
    with LOCK:
        return read_db()['cases']

@router.get('/cases/{case_id}')
def view_case(case_id: str):
    with LOCK:
        data = read_db()
        case = get_case(data, case_id)
        return {**case, 'attempts': [a for a in data['attempts'] if a['caseId'] == case_id]}

@router.get('/cases/{case_id}/documents/{filename}')
def document(case_id: str, filename: str):
    with LOCK:
        case = get_case(read_db(), case_id)
    if filename not in case['documents'] or Path(filename).name != filename:
        raise HTTPException(404, 'Document not found')
    path = evidence_path(case, filename)
    return FileResponse(path, media_type='application/pdf', filename=filename, content_disposition_type='inline')

@router.post('/cases/{case_id}/ai-process')
def ai_process(case_id: str):
    with LOCK:
        case = get_case(read_db(), case_id)
    started = time.perf_counter()
    text = case_text(case)
    regex = extract_fields(text)
    fields, extraction = extract_fields_with_gemini(text, regex)
    missing = find_missing_fields(fields)
    fallback = route_claim(fields, missing)
    routing, routing_status = route_claim_with_gemini(text, fields, missing, fallback)
    seconds = round(time.perf_counter() - started, 3)
    result = {'id': uuid4().hex, 'caseId': case_id, 'fields': fields, 'missingFields': missing, 'recommendedRoute': routing['route'], 'reasoning': routing['reasoning'], 'extractionStatus': extraction, 'routingStatus': routing_status, 'apiSeconds': seconds, 'processedAt': now()}
    with LOCK:
        data = read_db()
        data.setdefault('aiRuns', []).append(result)
        write_db(data)
    return result

@router.post('/attempts')
def submit_attempt(body: Submission):
    if body.mode not in ('manual', 'ai'):
        raise HTTPException(400, 'Invalid processing mode')
    if body.finalRoute not in ROUTES:
        raise HTTPException(400, 'Invalid routing decision')
    with LOCK:
        data = read_db()
        case = get_case(data, body.caseId)
        ai_run = None
        if body.mode == 'ai':
            ai_run = next((r for r in data.get('aiRuns', []) if r['id'] == body.aiAttemptId and r['caseId'] == body.caseId), None)
            if not ai_run:
                raise HTTPException(400, 'Run the AI analysis before submitting an AI attempt')
        if ai_run and ai_run['recommendedRoute'] != body.finalRoute and not body.decisionReason.strip():
            raise HTTPException(400,'Override reason required')
        clean_fields = {str(k): str(v)[:5000] if v is not None else '' for k, v in body.fields.items()}
        attempt = {'id': uuid4().hex, 'caseId': body.caseId, 'mode': body.mode, 'elapsedSeconds': round(body.elapsedSeconds, 2), 'fields': clean_fields, 'missingFields': find_missing_fields(clean_fields), 'finalRoute': body.finalRoute, 'decisionReason': body.decisionReason[:2000], 'submittedAt': now(), 'quality': score(clean_fields, body.finalRoute, body.caseId), 'reviewStage': 'Handler approved', 'humanApproved': True}
        if ai_run:
            attempt.update({'aiAttemptId': ai_run['id'], 'apiSeconds': ai_run['apiSeconds'], 'aiRecommendedRoute': ai_run['recommendedRoute'], 'overridden': ai_run['recommendedRoute'] != body.finalRoute, 'correctedFields': sum(str(clean_fields.get(k) or '') != str(v or '') for k, v in ai_run['fields'].items()), 'extractionMethod': ai_run['extractionStatus'].get('method'), 'routingMethod': ai_run['routingStatus'].get('method')})
        data['attempts'].append(attempt)
        case['status'] = 'Specialist referral' if body.finalRoute == 'Specialist Queue' else 'Reviewed'
        write_db(data)
        return attempt

class Revision(BaseModel):
    basedOnAttemptId: str
    fields: dict = Field(default_factory=dict)
    finalRoute: str
    decisionReason: str

@router.post('/cases/{case_id}/revisions')
def save_revision(case_id: str, body: Revision):
    if body.finalRoute not in ROUTES:
        raise HTTPException(400, 'Invalid routing decision')
    if not body.decisionReason.strip():
        raise HTTPException(400, 'A correction reason is required')
    with LOCK:
        data = read_db()
        case = get_case(data, case_id)
        prior = next((a for a in data['attempts'] if a['id'] == body.basedOnAttemptId and a['caseId'] == case_id), None)
        if not prior:
            raise HTTPException(404, 'Saved review version not found')
        clean_fields = {str(k): str(v)[:5000] if v is not None else '' for k,v in body.fields.items()}
        revision = {
            'id': uuid4().hex, 'caseId': case_id, 'mode': prior['mode'],
            'isRevision': True, 'basedOnAttemptId': prior['id'],
            'elapsedSeconds': 0, 'fields': clean_fields,
            'missingFields': find_missing_fields(clean_fields),
            'finalRoute': body.finalRoute, 'decisionReason': body.decisionReason[:2000],
            'submittedAt': now(), 'quality': score(clean_fields, body.finalRoute, case_id),
            'reviewStage': 'Handler corrected', 'humanApproved': True,
            'aiRecommendedRoute': prior.get('aiRecommendedRoute'),
            'overridden': prior.get('aiRecommendedRoute') is not None and prior.get('aiRecommendedRoute') != body.finalRoute,
        }
        data['attempts'].append(revision)
        case['status'] = 'Specialist referral' if body.finalRoute == 'Specialist Queue' else 'Reviewed'
        write_db(data)
        return revision

@router.get('/attempts')
def attempts():
    with LOCK:
        return read_db()['attempts']

@router.post('/reset')
def reset():
    with LOCK:
        write_db(initial())
    return {'message': 'Synthetic workbench cases and attempts reset; user-uploaded PDFs remain on disk but are no longer listed'}
