"""macOS per-login installer. Build first, stop old agents, snapshot, health-check, rollback.

Never run imported project text as instructions. Paths are explicit argument lists.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
BASE = Path.home() / 'Library/Application Support'
TARGET = BASE / f'ClaimsFlow-v{VERSION}'
AGENTS = Path.home() / 'Library/LaunchAgents'
LABEL = f'uk.claimsflow.v{VERSION}'
DOMAIN = f'gui/{os.getuid()}'
HTTP = build_opener(ProxyHandler({}))


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def listening(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def ready(host, port, instance):
    try:
        with HTTP.open(f'http://{host}:{port}/ready', timeout=2) as response:
            data = json.load(response)
        return data == {'ok': True, 'version': VERSION, 'instance': instance}
    except (OSError, ValueError):
        return False


def snapshot(source, destination):
    """SQLite backup includes committed WAL contents; validates the copied database."""
    with sqlite3.connect(f'{source.resolve().as_uri()}?mode=ro', uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError(f'Corrupt database: {source}')
    destination.chmod(0o600)


def copy_data(source, destination):
    if not source.is_dir():
        raise RuntimeError(f'Missing previous data folder: {source}')
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.sqlite3', '*-wal', '*-shm', '*.tmp', '*.setup-lock'))
    for db in source.rglob('*.sqlite3'):
        out = destination / db.relative_to(source)
        out.parent.mkdir(parents=True, exist_ok=True)
        snapshot(db, out)


def previous_install():
    candidates = [p for p in BASE.glob('ClaimsFlow-v*') if p.is_dir() and p != TARGET]
    def version(path):
        try:
            return tuple(int(n) for n in path.name.split('-v')[1].split('.'))
        except ValueError:
            return ()
    current_version = tuple(map(int, VERSION.split('.')))
    candidates = [p for p in candidates if version(p) and version(p) < current_version]
    return max(candidates, key=version) if candidates else None


def write_launchers(host, port, instance):
    config = {'host': host, 'port': port, 'instance': instance, 'version': VERSION}
    (TARGET / 'install.json').write_text(json.dumps(config, indent=2))
    service = TARGET / 'RUN_SERVICE.command'
    service.write_text('''#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
BASE="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE/app/backend"
exec "$BASE/app/backend/.venv/bin/python" installed_server.py "$BASE"
''')
    recovery = TARGET / 'RECOVER_ADMIN_PASSWORD.command'
    recovery.write_text('''#!/bin/bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
export CLAIMSFLOW_ACCOUNTS_DB="$BASE/accounts.sqlite3"
cd "$BASE/app/backend"
exec "$BASE/app/backend/.venv/bin/python" local_recovery.py
''')
    shortcuts = Path.home() / f'Applications/ClaimsFlow v{VERSION}'
    shortcuts.mkdir(parents=True, exist_ok=True)
    for name, script in [('Open ClaimsFlow.command', f'#!/bin/bash\nopen "http://{host}:{port}/"\n'),
                          ('Recover Admin Password.command', '#!/bin/bash\nexec /bin/bash "' + str(recovery).replace('"', '\\"').replace('$', '\\$').replace('`', '\\`') + '"\n')]:
        path = shortcuts / name
        path.write_text(script)
        path.chmod(0o700)
    for path in (service, recovery):
        path.chmod(0o700)
    AGENTS.mkdir(parents=True, exist_ok=True)
    agent = AGENTS / f'{LABEL}.plist'
    with agent.open('wb') as out:
        plistlib.dump({'Label': LABEL, 'ProgramArguments': ['/bin/bash', str(service)],
                      'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 10,
                      'StandardOutPath': str(TARGET/'server.log'),
                      'StandardErrorPath': str(TARGET/'server-error.log')}, out)
    agent.chmod(0o600)
    return agent


def install(host, port, previous=None):
    if sys.platform != 'darwin':
        raise RuntimeError('Run this installer on the Mac mini, not Linux or Windows.')
    if sys.version_info < (3, 11):
        raise RuntimeError('Python 3.11 or newer is required.')
    address = ipaddress.ip_address(host)
    if address.version != 4 or not (address.is_private or address.is_loopback) or address.is_unspecified:
        raise ValueError('Use a private IPv4 address assigned to the Mac mini by ZeroTier, or 127.0.0.1.')
    if not 1024 <= port <= 65535:
        raise ValueError('Port must be between 1024 and 65535.')
    if not shutil.which('npm'):
        raise RuntimeError('Install Node.js 22 LTS (including npm) first.')
    if TARGET.exists():
        config = json.loads((TARGET/'install.json').read_text()) if (TARGET/'install.json').exists() else {}
        if config and ready(config['host'], config['port'], config['instance']):
            url = f"http://{config['host']}:{config['port']}/"
            print(f'This release is already installed and healthy: {url} No data changed.', flush=True)
            subprocess.run(['open', url])
            return
        raise RuntimeError(f'{TARGET} already exists but is not healthy. Read server-error.log; no files changed. See README rollback steps.')
    # A wrong/offline ZeroTier address must fail before stopping the working app.
    try:
        with socket.socket() as probe:
            probe.bind((host, 0))
    except OSError as exc:
        raise RuntimeError(f'{host} is not assigned to this Mac. Check ZeroTier or pass --host.') from exc
    prior = Path(previous).expanduser().resolve(strict=True) if previous else previous_install()
    if prior and (prior == TARGET or not (prior/'data').is_dir()):
        raise ValueError('Previous installation must be a different release containing a data folder')
    print(f'Previous installation: {prior or "none (fresh install)"}', flush=True)
    stopped = []
    legacy = []
    agent = AGENTS / f'{LABEL}.plist'
    started = False
    try:
        TARGET.mkdir(parents=True, mode=0o700)
        app = TARGET/'app'
        app.mkdir()
        for name in ('backend', 'src', 'mac'):
            shutil.copytree(ROOT/name, app/name, ignore=shutil.ignore_patterns('.venv', '__pycache__', '.pytest_cache'))
        for name in ('package.json', 'package-lock.json', 'vite.config.js', 'index.html'):
            shutil.copy2(ROOT/name, app/name)
        shutil.copy2(ROOT/'VERSION', TARGET/'VERSION')
        # The installed app includes mac/install.py and its regression tests.
        # Keep their source manifest alongside package.json, as in the ZIP.
        shutil.copy2(ROOT/'VERSION', app/'VERSION')
        # Create the virtualenv in its final path: pip/uvicorn shebangs remain valid.
        run(sys.executable, '-m', 'venv', app/'backend/.venv')
        python = app/'backend/.venv/bin/python'
        run(python, '-m', 'pip', 'install', '-r', app/'backend/requirements-lock.txt')
        run('npm', 'ci', '--no-audit', '--no-fund', cwd=app)
        run('npm', 'run', 'build', cwd=app)
        if not (app/'dist/index.html').is_file():
            raise RuntimeError('Frontend build produced no index.html')
        testenv = {**os.environ, 'CLAIMSFLOW_DATA_DIR': str(TARGET/'test-data')}
        run(python, '-m', 'pytest', '-q', cwd=app/'backend', env=testenv)
        shutil.rmtree(TARGET/'test-data', ignore_errors=True)
        # Stop every loaded legacy ClaimsFlow job, including v11.6 and v11.7.
        # Leave unrelated jobs and all legacy files intact.
        for old in sorted(AGENTS.glob('*claimsflow*.plist')):
            if old == agent:
                continue
            with old.open('rb') as f:
                old_label = plistlib.load(f).get('Label')
            legacy.append(old)
            if old_label and subprocess.run(['launchctl', 'print', f'{DOMAIN}/{old_label}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                run('launchctl', 'bootout', DOMAIN, old)
                stopped.append(old)
        for _ in range(10):
            if not listening(host, port):
                break
            time.sleep(1)
        if listening(host, port):
            raise RuntimeError('Port is still occupied. A manually started app may be running. No process was killed.')
        data = TARGET/'data'
        data.mkdir(mode=0o700)
        if prior:
            # Capture after stopping all managed writers. Prior directory is the rollback copy.
            copy_data(prior/'data', data)
            accounts = prior/'accounts.sqlite3'
            if accounts.is_file():
                snapshot(accounts, TARGET/'accounts.sqlite3')
                # Explicit schema upgrade; existing users remain analysts unless already admin.
                run(python, '-c', 'from accounts import initialize; from pathlib import Path; import sys; initialize(Path(sys.argv[1]))', TARGET/'accounts.sqlite3', cwd=app/'backend')
            else:
                print('No accounts database found in the selected previous release. Use local recovery to create the administrator.', flush=True)
        for source in (ROOT/'backend/data/evidence').rglob('*'):
            if source.is_file():
                out = data/'evidence'/source.relative_to(ROOT/'backend/data/evidence')
                out.parent.mkdir(parents=True, exist_ok=True)
                if not out.exists():
                    shutil.copy2(source, out)
        instance = uuid4().hex
        agent = write_launchers(host, port, instance)
        run('launchctl', 'bootstrap', DOMAIN, agent)
        started = True
        for _ in range(60):
            if ready(host, port, instance):
                # Disable old autostarts only after verifying this exact running release.
                for old in legacy:
                    old.rename(old.with_suffix('.plist.disabled'))
                print(f'ClaimsFlow {VERSION} ready: http://{host}:{port}/\n'
                      f'Accounts: ~/Applications/ClaimsFlow v{VERSION}/Recover Admin Password.command\n'
                      f'Editable source: {TARGET}/app\nPrevious release retained: {prior}', flush=True)
                subprocess.run(['open', f'http://{host}:{port}/'])
                return
            time.sleep(1)
        raise RuntimeError(f'New release failed its health check. Inspect {TARGET}/server-error.log')
    except BaseException:
        if started:
            subprocess.run(['launchctl', 'bootout', DOMAIN, agent], stderr=subprocess.DEVNULL)
        if agent.exists():
            agent.unlink()
        # Build-only failures have no data to retain; migration/startup failures do.
        if TARGET.exists():
            failed = TARGET.with_name(TARGET.name+'.failed-'+uuid4().hex[:8])
            TARGET.rename(failed)
            print(f'Failed installation retained for diagnosis: {failed}', file=sys.stderr)
        for old in legacy:
            disabled = old.with_suffix('.plist.disabled')
            if disabled.exists():
                disabled.rename(old)
        for old in stopped:
            subprocess.run(['launchctl', 'bootstrap', DOMAIN, old], check=False)
        print('Previous loaded services restored where possible. No old data directory was overwritten.', file=sys.stderr)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1', help='Host IPv4 address, typically the private ZeroTier address for remote access')
    parser.add_argument('--previous', help='Explicit previous installation folder, if the newest version does not contain your working data')
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    os.umask(0o077)
    lock = BASE/'.claimsflow-install-lock'
    BASE.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        raise SystemExit(f'Another installer may be running. If none is, remove the stale lock: {lock}')
    try:
        install(args.host, args.port, args.previous)
    except Exception as exc:
        print(f'INSTALLATION FAILED: {exc}', file=sys.stderr)
        sys.exit(1)
    finally:
        lock.rmdir()
