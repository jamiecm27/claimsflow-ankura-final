"""ClaimsFlow v7 API. Synthetic demonstration data only."""
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import os
import zipfile
import io
import sqlite3
from collections import OrderedDict
from threading import Lock
import time
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from security import require_authorization
from v9_access import authorize as authorize_v9
from v9_sessions import protect as protect_v9_session, login as login_v9, logout as logout_v9, current as current_v9
from pydantic import BaseModel, Field
from core import route_claim, make_claim, metrics, QUEUES
from storage_config import create_store
from ai import analyze, test_connection, active_model
from keychain_store import get_gemini_key, save_gemini_key

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('CLAIMSFLOW_ACCOUNTS_DB', str(Path(os.environ.get('CLAIMSFLOW_DATA_DIR', str(ROOT / 'data'))).parent / 'accounts.sqlite3'))
store = create_store(Path(os.environ.get('CLAIMSFLOW_DATA_DIR', str(ROOT / 'data'))))
APP_VERSION = (ROOT.parent / 'VERSION').read_text(encoding='utf-8').strip()
app = FastAPI(title=f'ClaimsFlow v{APP_VERSION}', version=f'{APP_VERSION}.0')

class LoginCredentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)

class FirstRunCredentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)

@app.get('/setup')
def first_run_page(request: Request):
    db = Path(os.environ.get('CLAIMSFLOW_ACCOUNTS_DB', ''))
    if db.is_file():
        return RedirectResponse('/login', status_code=303)
    if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, 'Initial setup is local-only')
    return FileResponse(ROOT / 'setup.html', headers={'Cache-Control':'no-store'})

@app.post('/api/setup')
def first_run_create(payload: FirstRunCredentials, request: Request):
    if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, 'Initial setup is local-only')
    origin = request.headers.get('origin')
    if origin and origin != str(request.base_url).rstrip('/'):
        raise HTTPException(403, 'Invalid origin')
    from accounts import initialize, add_user
    db = Path(os.environ['CLAIMSFLOW_ACCOUNTS_DB'])
    if db.exists():
        raise HTTPException(409, 'Already configured')
    if not payload.username or len(payload.password) < 12:
        raise HTTPException(400, 'Username and password of at least 12 characters required')
    lock = db.with_suffix('.setup-lock')
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise HTTPException(409, 'Setup already in progress')
    os.close(fd)
    try:
        if db.exists():
            raise HTTPException(409, 'Already configured')
        initialize(db)
        try:
            add_user(db, payload.username.strip(), payload.password, 'admin')
        except ValueError as exc:
            db.unlink(missing_ok=True)
            raise HTTPException(400, str(exc))
    finally:
        lock.unlink(missing_ok=True)
    return {'ok': True, 'next': '/login'}

@app.get('/login')
def login_page():
    return FileResponse(ROOT / 'login.html', headers={'Cache-Control': 'no-store'})

_login_attempts = OrderedDict()
_login_lock = Lock()

@app.post('/api/login')
def session_login(payload: LoginCredentials, request: Request):
    if os.environ.get('CLAIMSFLOW_AUTH_MODE', 'sessions') != 'sessions':
        raise HTTPException(404)
    if request.headers.get('origin') and request.headers['origin'] != str(request.base_url).rstrip('/'):
        raise HTTPException(403, 'Invalid origin')
    peer = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    with _login_lock:
        attempts = [t for t in _login_attempts.get(peer, []) if now-t < 60]
        if len(attempts) >= 10:
            raise HTTPException(429, 'Too many sign-in attempts. Wait one minute.', headers={'Retry-After':'60'})
        attempts.append(now)
        _login_attempts[peer] = attempts
        _login_attempts.move_to_end(peer)
        while len(_login_attempts) > 1024:
            _login_attempts.popitem(last=False)
    db = os.environ.get('CLAIMSFLOW_ACCOUNTS_DB', '')
    token = login_v9(db, payload.username, payload.password)
    if not token:
        raise HTTPException(401, 'Invalid credentials')
    response = JSONResponse({'ok': True})
    response.set_cookie('cf9_session', token, httponly=True, secure=os.environ.get('CLAIMSFLOW_HTTPS') == '1', samesite='strict', max_age=28800, path='/')
    response.headers['Cache-Control'] = 'no-store'
    return response

class PasswordChange(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)

class AccountCreate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)
    role: str = 'analyst'

class AccountReset(BaseModel):
    new_password: str = Field(min_length=12, max_length=1024)

@app.get('/forgot-password')
def forgot_password():
    return FileResponse(ROOT / 'forgot.html', headers={'Cache-Control': 'no-store'})

@app.get('/account')
def account_page():
    return FileResponse(ROOT / 'account.html', headers={'Cache-Control': 'no-store'})

@app.post('/api/account/password')
def change_password(payload: PasswordChange, request: Request):
    from accounts import verify_user, set_password
    from v9_sessions import invalidate_user
    user = current_v9(request)
    db = Path(os.environ['CLAIMSFLOW_ACCOUNTS_DB'])
    if not user or not verify_user(db, user, payload.current_password):
        raise HTTPException(401, 'Current password incorrect')
    try:
        set_password(db, user, payload.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    invalidate_user(user)
    return {'ok': True, 'message': 'Password changed. Sign in again.'}

@app.get('/api/admin/users')
def admin_users(request: Request):
    from accounts import get_role, list_users
    db = Path(os.environ['CLAIMSFLOW_ACCOUNTS_DB'])
    if get_role(db, current_v9(request) or '') != 'admin':
        raise HTTPException(403, 'Administrator required')
    return {'users': list_users(db)}

@app.post('/api/admin/users')
def admin_add_user(payload: AccountCreate, request: Request):
    from accounts import get_role, add_user
    db = Path(os.environ['CLAIMSFLOW_ACCOUNTS_DB'])
    if get_role(db, current_v9(request) or '') != 'admin':
        raise HTTPException(403, 'Administrator required')
    try:
        add_user(db, payload.username.strip(), payload.password, payload.role)
    except (ValueError, __import__('sqlite3').IntegrityError) as e:
        raise HTTPException(400, str(e))
    return {'ok': True}

@app.post('/api/admin/users/{username}/password')
def admin_reset_password(username: str, payload: AccountReset, request: Request):
    from accounts import get_role, set_password
    from v9_sessions import invalidate_user
    db = Path(os.environ['CLAIMSFLOW_ACCOUNTS_DB'])
    if get_role(db, current_v9(request) or '') != 'admin':
        raise HTTPException(403, 'Administrator required')
    try:
        set_password(db, username, payload.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    invalidate_user(username)
    return {'ok': True}

@app.post('/api/logout')
def session_logout(request: Request):
    logout_v9(request)
    response = JSONResponse({'ok': True})
    response.delete_cookie('cf9_session', path='/')
    return response

@app.get('/api/me')
def session_me(request: Request):
    from accounts import get_role
    user = current_v9(request)
    return {'username': user, 'role': get_role(Path(os.environ['CLAIMSFLOW_ACCOUNTS_DB']), user) if user else None}

@app.middleware('http')
async def private_access(request: Request, call_next):
    mode = os.environ.get("CLAIMSFLOW_AUTH_MODE", "sessions")
    denied = protect_v9_session(request) if mode == "sessions" else (authorize_v9(request) if mode == "accounts" else JSONResponse({"detail":"Invalid authentication mode"}, status_code=503))
    if denied is not None:
        return denied
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response

class ClaimInput(BaseModel):
    claimant: str = Field(min_length=1, max_length=120)
    policy_number: str = Field(min_length=1, max_length=100)
    claim_type: str
    estimated_damage: float = Field(ge=0)
    description: str = Field(default='', max_length=5000)

class ReviewInput(BaseModel):
    claim_id: str
    mode: str
    final_route: str
    elapsed_seconds: float = Field(ge=0)
    notes: str = ''
    ai_provider: str | None = None
    ai_seconds: float | None = None
    override_reason: str = ''
    reviewed_fields: dict = Field(default_factory=dict)

class Settings(BaseModel):
    hourly_rate: float = Field(default=32, ge=0)
    api_cost: float = Field(default=0.04, ge=0)
    human_minutes: float = Field(default=18, ge=0)
    ai_check_minutes: float = Field(default=3, ge=0)
    monthly_volume: int = Field(default=1000, ge=0)

settings = Settings()

@app.get('/ready')
def ready():
    # No customer, credential, or configuration details in the public probe.
    return {'ok': True, 'version': APP_VERSION, 'instance': os.environ.get('CLAIMSFLOW_INSTANCE', '')}

@app.get('/api/health')
def health():
    return {'ok': True, 'version': f'{APP_VERSION}.0', 'gemini_configured': bool(get_gemini_key())}

class GeminiKeyInput(BaseModel):
    api_key: str = Field(min_length=15, max_length=500)

@app.get('/api/gemini-settings')
def gemini_settings():
    return {'configured': bool(get_gemini_key()),
            'model': active_model()}

@app.post('/api/gemini-test')
def gemini_test():
    return test_connection()

@app.post('/api/gemini-settings')
def save_gemini_settings(payload: GeminiKeyInput):
    # The backend is bound to 127.0.0.1 by the launcher; never expose this
    # credential-writing endpoint on a public or shared network interface.
    key = payload.api_key.strip()
    if not key or any(c.isspace() for c in key) or '\x00' in key:
        raise HTTPException(422, 'Enter a valid API key without spaces.')
    try:
        save_gemini_key(key)
    except Exception as exc:
        raise HTTPException(503, 'Unable to save in macOS Keychain. Check Keychain access and try again.') from exc
    return {'configured': True, 'saved': True}

@app.get('/api/claims')
def claims():
    return store.read()['claims']

@app.post('/api/claims')
def create_claim(payload: ClaimInput):
    def change(data):
        existing = [int(c['id'].split('-')[-1]) for c in data['claims'] if c['id'].split('-')[-1].isdigit()]
        claim = {'id': f'CLM-{max(existing, default=0)+1:04d}', **payload.model_dump(), 'status': 'New', 'created_at': datetime.now(timezone.utc).isoformat(), 'documents': []}
        claim['suggested_route'], _ = route_claim(claim)
        data['claims'].append(claim)
        return claim
    return store.update(change)

@app.post('/api/claims/{claim_id}/analyze')
def analyze_claim(claim_id: str):
    claim = next((c for c in store.read()['claims'] if c['id'] == claim_id), None)
    if not claim:
        raise HTTPException(404, 'Claim not found')
    return analyze(claim)

@app.get('/api/reviews')
def reviews():
    return store.read()['reviews']

@app.post('/api/reviews')
def add_review(payload: ReviewInput):
    if payload.mode not in ('manual', 'ai') or payload.final_route not in QUEUES:
        raise HTTPException(422, 'Invalid review mode or route')
    def change(data):
        claim = next((c for c in data['claims'] if c['id'] == payload.claim_id), None)
        if not claim:
            raise HTTPException(404, 'Claim not found')
        if payload.mode == 'ai' and payload.ai_provider not in ('gemini', 'rules_fallback'):
            raise HTTPException(422, 'AI provider must be identified')
        if payload.mode == 'ai' and payload.final_route != claim['suggested_route'] and not payload.override_reason.strip():
            raise HTTPException(422, 'An override reason is required')
        record = {'id': str(uuid4()), **payload.model_dump(), 'reference_route': claim['suggested_route'], 'created_at': datetime.now(timezone.utc).isoformat()}
        data['reviews'].append(record)
        claim['status'] = 'Reviewed'
        return record
    return store.update(change)

@app.get('/api/evaluation')
def evaluation():
    return {'metrics': metrics(store.read()['reviews'], settings.hourly_rate, settings.api_cost, settings.human_minutes, settings.ai_check_minutes), 'settings': settings.model_dump()}

@app.put('/api/settings')
def update_settings(value: Settings):
    global settings
    settings = value
    return settings

@app.post('/api/admin/generate')
def generate(count: int = 100):
    if not 1 <= count <= 100:
        raise HTTPException(422, 'Count must be between 1 and 100')
    def change(data):
        existing = [int(c['id'].split('-')[-1]) for c in data['claims'] if c['id'].split('-')[-1].isdigit()]
        start = max(existing, default=0) + 1
        data['claims'].extend(make_claim(i) for i in range(start, start + count))
        return {'created': count, 'total': len(data['claims'])}
    return store.update(change)

@app.post('/api/admin/reset')
def reset():
    from core import sample_claims
    store.save({'claims': sample_claims(), 'reviews': []})
    return {'ok': True, 'note': 'Synthetic demonstration data reset'}

from compat import router as workbench_compat_router
app.include_router(workbench_compat_router)

# Production frontend: API, PDF routes and UI share the same origin/port.
DIST = ROOT.parent / 'dist'
if DIST.is_dir():
    app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='assets')

    @app.get('/')
    def home():
        return FileResponse(DIST / 'index.html')
