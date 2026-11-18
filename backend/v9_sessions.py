"""Opt-in v9 login sessions, local-only unless placed behind trusted HTTPS proxy."""
import os, secrets, time
from pathlib import Path
from threading import Lock
from fastapi.responses import JSONResponse, RedirectResponse
from accounts import verify_user, get_role, session_identity

_sessions = {}
_lock = Lock()
TTL = 8 * 3600

def login(db, username, password):
    if not Path(db).is_file():
        return None
    identity = session_identity(Path(db), username)
    if not identity or not verify_user(Path(db), username, password) or identity != session_identity(Path(db), username):
        return None
    token = secrets.token_urlsafe(40)
    with _lock:
        for expired, item in list(_sessions.items()):
            if time.monotonic() > item[1]:
                _sessions.pop(expired, None)
        _sessions[token] = (username, time.monotonic() + TTL, str(Path(db).resolve()), identity)
    return token

def current(request):
    token = request.cookies.get('cf9_session', '')
    with _lock:
        item = _sessions.get(token)
        if not item:
            return None
        if time.monotonic() > item[1]:
            _sessions.pop(token, None)
            return None
    db = os.environ.get('CLAIMSFLOW_ACCOUNTS_DB', '')
    if not Path(db).is_file() or str(Path(db).resolve()) != item[2] or session_identity(Path(db), item[0]) != item[3]:
        logout(request)
        return None
    return item[0]

def logout(request):
    with _lock:
        _sessions.pop(request.cookies.get('cf9_session', ''), None)

def protect(request):
    if request.url.path in ('/login', '/api/login', '/setup', '/api/setup', '/forgot-password', '/ready'):
        return None
    user = current(request)
    if not user:
        if not Path(os.environ.get('CLAIMSFLOW_ACCOUNTS_DB', '/nonexistent')).exists():
            return RedirectResponse('/login', status_code=303) if not request.url.path.startswith(('/api/', '/workbench/')) else JSONResponse({'detail':'Create the administrator using Recover Admin Password.command on the Mac mini'}, status_code=403)
        if request.url.path.startswith('/api/') or request.url.path.startswith('/workbench/'):
            return JSONResponse({'detail':'Login required'}, status_code=401, headers={'Cache-Control':'no-store'})
        return RedirectResponse('/login', status_code=303)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'Origin rejected'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail':'Cross-site request rejected'}, status_code=403)
        if request.url.path.startswith(('/api/admin/', '/api/settings', '/api/gemini-settings', '/api/gemini-test', '/workbench/reset')):
            if get_role(Path(os.environ['CLAIMSFLOW_ACCOUNTS_DB']), user) != 'admin':
                return JSONResponse({'detail':'Administrator required'}, status_code=403)
    return None


def invalidate_user(username):
    with _lock:
        for token, item in list(_sessions.items()):
            if item[0] == username:
                _sessions.pop(token, None)
