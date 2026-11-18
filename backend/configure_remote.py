"""One-time macOS graphical setup. No API keys are copied."""
import json, secrets, hashlib, subprocess, ipaddress
from pathlib import Path

def dialog(prompt, hidden=False, default=''):
    # osascript receives the prompt as an argument, not interpolated source.
    script = 'on run argv\nset promptText to item 1 of argv\nset defaultText to item 2 of argv\nreturn text returned of (display dialog promptText default answer defaultText ' + ('with hidden answer ' if hidden else '') + 'buttons {"Cancel", "OK"} default button "OK")\nend run'
    result = subprocess.run(['osascript','-e',script,prompt,default], capture_output=True, text=True)
    if result.returncode: raise SystemExit('Setup cancelled.')
    return result.stdout.strip()

print('ClaimsFlow v8 ZeroTier setup')
address = dialog('Enter this Mac mini ZeroTier IPv4 address:')
try:
    ip = ipaddress.ip_address(address)
    if ip.version != 4 or ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_global:
        raise ValueError()
except ValueError:
    raise SystemExit('Enter the private IPv4 address assigned to this Mac by ZeroTier.')
username = dialog('Choose a ClaimsFlow login username:', default='claimsflow')
if not username or ':' in username: raise SystemExit('Invalid username.')
password = dialog('Choose a strong ClaimsFlow password (share privately with the authorised remote user):', hidden=True)
if len(password) < 12: raise SystemExit('Use at least 12 characters.')
salt = secrets.token_bytes(16)
config = {'bind_ip':address, 'username':username, 'salt':salt.hex(), 'password_hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,250000).hex()}
path = Path.home()/'Library'/'Application Support'/'ClaimsFlow'/'config.json'
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(config,indent=2))
path.chmod(0o600)
print(f'Saved private access configuration. Restart ClaimsFlow, then use http://{address}:8765/ on BOTH Macs.')
print('IMPORTANT: Use ZeroTier access rules to allow only authorised remote devices and the host Mac; never forward this port publicly.')
