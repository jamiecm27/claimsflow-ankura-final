"""Opt-in v9 account authentication and minimal role authorization.

Enable with CLAIMSFLOW_AUTH_MODE=accounts and CLAIMSFLOW_ACCOUNTS_DB pointing
at a provisioned SQLite account store. Never silently fall back to anonymous.
Uses HTTP Basic over private transport; production deployments should use TLS.
"""
import base64
import os
from pathlib import Path
from fastapi.responses import JSONResponse
from accounts import verify_user, get_role


def authorize(request):
    db_path = os.environ.get('CLAIMSFLOW_ACCOUNTS_DB', '')
    if not db_path or not Path(db_path).is_file():
        return JSONResponse({'detail': 'Accounts database unavailable'}, status_code=503)
    auth = request.headers.get('authorization', '')
    try:
        scheme, token = auth.split(' ', 1)
        if scheme.lower() != 'basic':
            raise ValueError('scheme')
        raw = base64.b64decode(token, validate=True).decode('utf-8')
        username, password = raw.split(':', 1)
        if not username or not password or not verify_user(Path(db_path), username, password):
            raise ValueError('credentials')
    except (ValueError, UnicodeError, KeyError, OverflowError):
        return JSONResponse({'detail': 'Authentication required'}, status_code=401,
                            headers={'WWW-Authenticate': 'Basic realm="ClaimsFlow v9"', 'Cache-Control': 'no-store'})
    # Role checks apply to administrative/configuration writes.
    restricted = ('/api/admin/', '/api/gemini-settings', '/api/settings', '/workbench/reset', '/api/gemini-test')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.url.path.startswith(restricted):
        if get_role(Path(db_path), username) != 'admin':
            return JSONResponse({'detail': 'Administrator role required'}, status_code=403)
    return None
