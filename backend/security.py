"""Private network authentication for ClaimsFlow v8."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from fastapi.responses import JSONResponse

def _config():
    path = os.environ.get('CLAIMSFLOW_CONFIG', '')
    if not path or not Path(path).is_file():
        return {}
    return json.loads(Path(path).read_text())

def require_authorization(request):
    config = _config()
    # Local-only setup can be used without auth. Remote mode refuses startup
    # without a configured password (see run_server.py).
    if not config.get('password_hash'):
        return None
    auth = request.headers.get('authorization', '')
    try:
        scheme, token = auth.split(' ', 1)
        if scheme.lower() != 'basic':
            raise ValueError()
        raw = base64.b64decode(token, validate=True).decode('utf-8')
        username, password = raw.split(':', 1)
        salt = bytes.fromhex(config['salt'])
        computed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 250000).hex()
        valid = hmac.compare_digest(username, config.get('username', '')) and hmac.compare_digest(computed, config['password_hash'])
        if valid:
            return None
    except (ValueError, KeyError, UnicodeError):
        pass
    return JSONResponse({'detail':'Authentication required'}, status_code=401, headers={'WWW-Authenticate':'Basic realm="ClaimsFlow v8"', 'Cache-Control':'no-store'})
