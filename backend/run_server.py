"""Run production server on localhost or an explicitly configured ZeroTier IP."""
import json
import os
import ipaddress
from pathlib import Path
import uvicorn

config_path = Path.home() / 'Library' / 'Application Support' / 'ClaimsFlow' / 'config.json'
config = json.loads(config_path.read_text()) if config_path.exists() else {}
host = config.get('bind_ip', '127.0.0.1')
try:
    ipaddress.ip_address(host)
except ValueError:
    raise SystemExit('Invalid bind IP in ClaimsFlow configuration')
if host not in ('127.0.0.1', '::1') and not config.get('password_hash') and os.environ.get('CLAIMSFLOW_AUTH_MODE') not in ('accounts', 'sessions'):
    raise SystemExit('Remote access requires a password. Run Configure Remote Access first.')
if os.environ.get('CLAIMSFLOW_AUTH_MODE') in ('accounts', 'sessions') and not os.environ.get('CLAIMSFLOW_ACCOUNTS_DB'):
    raise SystemExit('Accounts mode requires CLAIMSFLOW_ACCOUNTS_DB')
os.environ['CLAIMSFLOW_CONFIG'] = str(config_path)
# Keep user data outside release directory for safe upgrades.
data = Path.home() / 'Library' / 'Application Support' / 'ClaimsFlow' / 'data'
data.mkdir(parents=True, exist_ok=True)
os.environ['CLAIMSFLOW_DATA_DIR'] = str(data)
uvicorn.run('app:app', host=host, port=int(os.environ.get('CLAIMSFLOW_PORT', '8765')), workers=1, proxy_headers=False)
