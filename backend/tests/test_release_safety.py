"""Regression checks for failures found in the v11.7 installer/code review."""
import importlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import zipfile

import pytest
from fastapi.testclient import TestClient
from accounts import initialize, add_user, get_role, set_password


@pytest.fixture
def site(tmp_path, monkeypatch):
    db = tmp_path/'accounts.sqlite3'
    initialize(db)
    add_user(db, 'owner', 'owner-test-passphrase', 'admin')
    add_user(db, 'analyst', 'analyst-test-passphrase', 'analyst')
    monkeypatch.setenv('CLAIMSFLOW_AUTH_MODE', 'sessions')
    monkeypatch.setenv('CLAIMSFLOW_ACCOUNTS_DB', str(db))
    monkeypatch.setenv('CLAIMSFLOW_DATA_DIR', str(tmp_path/'data'))
    import compat
    import app
    importlib.reload(compat)
    importlib.reload(app)
    with TestClient(app.app) as client:
        yield client, app, compat, db


def sign_in(client, name='owner'):
    assert client.post('/api/login', json={'username':name, 'password':f'{name}-test-passphrase'}).status_code == 200


def test_analyst_cannot_reset_real_ui_data(site):
    client, app, compat, db = site
    sign_in(client, 'analyst')
    before = compat.storage.read()
    assert client.post('/workbench/reset').status_code == 403
    assert compat.storage.read() == before
    assert client.post('/api/admin/reset').status_code == 403
    assert client.post('/api/gemini-test').status_code == 403
    assert client.get('/api/me').json()['role'] == 'analyst'
    assert client.get('/api/admin/users').status_code == 403


def test_local_password_recovery_revokes_existing_sessions(site):
    client, app, compat, db = site
    sign_in(client)
    # Separate recovery process writes the database, without touching _sessions.
    set_password(db, 'owner', 'replacement-passphrase')
    assert client.get('/api/me').status_code == 401
    assert client.post('/api/login', json={'username':'owner','password':'owner-test-passphrase'}).status_code == 401
    assert client.post('/api/login', json={'username':'owner','password':'replacement-passphrase'}).status_code == 200


def test_inactive_account_loses_session(site):
    client, app, compat, db = site
    sign_in(client)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE users SET active=0 WHERE username='owner'")
    assert client.get('/workbench/cases').status_code == 401


def test_login_throttled_before_unbounded_password_hashing(site):
    client, app, compat, db = site
    for _ in range(10):
        assert client.post('/api/login', json={'username':'owner','password':'wrong'}).status_code == 401
    assert client.post('/api/login', json={'username':'owner','password':'wrong'}).status_code == 429


def test_cross_origin_logout_is_rejected(site):
    client, app, compat, db = site
    sign_in(client)
    assert client.post('/api/logout', headers={'Origin':'https://other.example'}).status_code == 403
    assert client.get('/api/me').json()['username'] == 'owner'


def test_restart_preserves_unreviewed_and_empty_data(site):
    _, _, compat, _ = site
    for claims in ([], [{'id':'CLM-0900','title':'Keep my upload','documents':[]} ]):
        original = {'claims':claims, 'reviews':[], 'evaluations':[{'id':'keep'}]}
        compat.storage.save(original)
        importlib.reload(compat)
        assert compat.storage.read() == original


def test_fresh_install_has_sample_cases(site):
    _, _, compat, _ = site
    assert compat.storage.read()['claims'] == compat.SAMPLE_CASES


def test_invalid_upload_does_not_create_empty_claim(site):
    client, _, compat, _ = site
    sign_in(client)
    before = compat.storage.read()
    assert client.post('/workbench/cases', data={'title':'bad'}, files={'documents':('not.pdf',b'bad','application/pdf')}).status_code == 422
    assert compat.storage.read() == before


def test_same_name_evidence_never_overwrites(site):
    client, _, compat, _ = site
    sign_in(client)
    first = client.post('/workbench/cases', data={'title':'test'}, files={'documents':('evidence.pdf',b'%PDF-first','application/pdf')}).json()
    second = client.post(f"/workbench/cases/{first['id']}/documents", files={'documents':('evidence.pdf',b'%PDF-second','application/pdf')}).json()
    assert len(set(second['documents'])) == 2
    blobs = [client.get(f"/workbench/cases/{first['id']}/documents/{name}").content for name in second['documents']]
    assert blobs == [b'%PDF-first', b'%PDF-second']


def test_zip_expansion_limit_checked_before_extract(site, monkeypatch):
    client, _, compat, _ = site
    sign_in(client)
    raw = io.BytesIO()
    with zipfile.ZipFile(raw,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for i in range(801):
            archive.writestr(f'claim/{i}.pdf', b'%PDF-small')
    assert client.post('/workbench/cases/bulk-import', files={'archive':('cases.zip',raw.getvalue(),'application/zip')}).status_code == 422


def test_health_probe_identifies_release_without_account_details(site, monkeypatch):
    client, app_module, _, _ = site
    monkeypatch.setenv('CLAIMSFLOW_INSTANCE','expected-instance')
    assert client.get('/ready').json() == {'ok':True,'version':app_module.APP_VERSION,'instance':'expected-instance'}
    assert client.get('/api/health').status_code == 401


def test_admin_reset_and_user_password_change(site):
    client, _, _, _ = site
    sign_in(client)
    assert client.post('/api/admin/users/analyst/password', json={'new_password':'a-new-user-passphrase'}).status_code == 200
    client.post('/api/logout')
    assert client.post('/api/login', json={'username':'analyst','password':'a-new-user-passphrase'}).status_code == 200
    assert client.post('/api/account/password', json={'current_password':'a-new-user-passphrase','new_password':'another-user-passphrase'}).status_code == 200
    assert client.get('/api/me').status_code == 401


def test_ai_receives_pdf_content_and_normalizes_fields(site, monkeypatch):
    client, _, compat, _ = site
    from google import genai
    import ai
    seen = []
    class Models:
        def generate_content(self, **kwargs):
            seen.append(kwargs)
            return SimpleNamespace(text=json.dumps({
                'route': 'Standard Queue',
                'reason': 'test',
                'fields': {
                    'policy_number': 'PDF-123',
                    'policyholder_name': '  Synthetic Policyholder  ',
                    'estimatedDamage': 0,
                    'description': None,
                    'unrelated': 'ignore',
                },
            }))
    monkeypatch.setattr(ai, 'get_gemini_key', lambda:'test-not-a-real-key')
    monkeypatch.setattr(ai, '_resolve', lambda *args, **kwargs:'fake-flash')
    monkeypatch.setattr(genai, 'Client', lambda **kwargs:SimpleNamespace(models=Models()))
    sign_in(client)
    case = client.post('/workbench/cases', data={'title':'sample'}, files={'documents':('test.pdf',b'%PDF-test-evidence','application/pdf')}).json()
    result = client.post(f"/workbench/cases/{case['id']}/ai-process").json()
    assert result['fields']['policyNumber'] == 'PDF-123'
    assert result['extractedFields'] == {
        'policyNumber': 'PDF-123', 'policyholderName': 'Synthetic Policyholder', 'estimatedDamage': '0',
    }
    schema = seen[0]['config'].response_json_schema
    assert 'policyholderName' in schema['properties']['fields']['required']
    assert seen[0]['contents'][0].inline_data.data == b'%PDF-test-evidence'
    saved = client.post('/workbench/attempts', json={
        'caseId': case['id'],
        'mode': 'ai',
        'elapsedSeconds': 5,
        'fields': {'policyNumber': 'CORRECTED'},
        'finalRoute': result['recommendedRoute'],
        'aiAttemptId': result['id'],
        'aiExtractedFields': result['extractedFields'],
    })
    assert saved.status_code == 200
    history = client.get(f"/workbench/cases/{case['id']}/history").json()['attempts']
    assert history[0]['fields']['policyNumber'] == 'CORRECTED'
    assert history[0]['aiExtractedFields']['policyNumber'] == 'PDF-123'


def test_local_rules_return_no_extracted_form_fields(site, monkeypatch):
    client, _, _, _ = site
    import ai
    monkeypatch.setattr(ai, 'get_gemini_key', lambda: '')
    sign_in(client)
    case = client.get('/workbench/cases').json()[0]
    result = client.post(f"/workbench/cases/{case['id']}/ai-process").json()
    assert result['provider'] == 'rules_fallback'
    assert result['extractedFields'] == {}


def load_installer():
    spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[2]/'mac/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installer_snapshot_includes_wal(tmp_path):
    install = load_installer()
    source = tmp_path/'live.sqlite3'
    with sqlite3.connect(source) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('CREATE TABLE records(value TEXT)')
        conn.execute("INSERT INTO records VALUES ('preserve me')")
        conn.commit()
        install.snapshot(source, tmp_path/'copy.sqlite3')
    with sqlite3.connect(tmp_path/'copy.sqlite3') as conn:
        assert conn.execute('SELECT value FROM records').fetchone()[0] == 'preserve me'


def test_installer_selects_latest_version_numerically(tmp_path, monkeypatch):
    install = load_installer()
    monkeypatch.setattr(install,'BASE',tmp_path)
    monkeypatch.setattr(install,'TARGET',tmp_path/f'ClaimsFlow-v{install.VERSION}')
    for name in ('11.2','11.6','11.7','11.8','11.9','12.0',install.VERSION,'12.0.failed-123','9.9'):
        (tmp_path/f'ClaimsFlow-v{name}').mkdir()
    assert install.previous_install().name == 'ClaimsFlow-v12.0'

def test_rerun_opens_existing_healthy_install(tmp_path, monkeypatch):
    install = load_installer()
    monkeypatch.setattr(install, 'TARGET', tmp_path)
    monkeypatch.setattr(install.sys, 'platform', 'darwin')
    monkeypatch.setattr(install.shutil, 'which', lambda _: '/fake/npm')
    (tmp_path/'install.json').write_text(json.dumps({
        'host': '127.0.0.1', 'port': 8879, 'instance': 'existing-release',
    }))
    monkeypatch.setattr(install, 'ready', lambda *args: args == ('127.0.0.1', 8879, 'existing-release'))
    calls = []
    monkeypatch.setattr(install.subprocess, 'run', lambda args: calls.append(args))
    install.install('192.168.0.42', 8767)
    assert calls == [['open', 'http://127.0.0.1:8879/']]


@pytest.mark.parametrize('startup_ok', [True, False])
def test_install_transition_and_rollback_simulated(tmp_path, monkeypatch, startup_ok):
    """Fake launchctl/npm/pip exercise orchestration, not macOS behaviour."""
    import plistlib
    install = load_installer()
    base = tmp_path/'Application Support'; base.mkdir()
    agents = tmp_path/'LaunchAgents'; agents.mkdir()
    prior = base/'ClaimsFlow-v12.0'
    (prior/'data').mkdir(parents=True)
    payload = '{"claims":[],"reviews":[]}'
    (prior/'data/workbench_v7.json').write_text(payload)
    initialize(prior/'accounts.sqlite3')
    add_user(prior/'accounts.sqlite3', 'migration_owner', 'fixture-password-12345', 'admin')
    for version in ('11.2','11.6','11.7','11.8','11.9','12.0'):
        with (agents/f'uk.claimsflow.v{version}.plist').open('wb') as out:
            plistlib.dump({'Label':f'uk.claimsflow.v{version}'},out)
    monkeypatch.setattr(install,'BASE',base)
    monkeypatch.setattr(install,'AGENTS',agents)
    monkeypatch.setattr(install,'TARGET',base/f'ClaimsFlow-v{install.VERSION}')
    monkeypatch.setattr(install.Path,'home',lambda:tmp_path)
    monkeypatch.setattr(install.sys,'platform','darwin')
    monkeypatch.setattr(install.shutil,'which',lambda name:'/fake/npm')
    monkeypatch.setattr(install.time,'sleep',lambda seconds:None)
    monkeypatch.setattr(install,'listening',lambda *args:False)
    monkeypatch.setattr(install,'ready',lambda *args:startup_ok)
    calls=[]
    def fake_run(*args, **kwargs):
        args=tuple(str(a) for a in args); calls.append(args)
        if args[:3] == ('npm','run','build'):
            dist=install.TARGET/'app/dist'; dist.mkdir()
            (dist/'index.html').write_text('test frontend placeholder')
    monkeypatch.setattr(install,'run',fake_run)
    def fake_subprocess(args, **kwargs):
        calls.append(tuple(str(a) for a in args))
        return SimpleNamespace(returncode=1 if args[:2]==['launchctl','print'] and args[-1].endswith('v11.2') else 0)
    monkeypatch.setattr(install.subprocess,'run',fake_subprocess)
    if startup_ok:
        install.install('127.0.0.1',8767)
        assert (install.TARGET/'data/workbench_v7.json').read_text() == payload
        assert get_role(install.TARGET/'accounts.sqlite3', 'migration_owner') == 'admin'
        assert (install.TARGET/'app/VERSION').read_text() == (install.ROOT/'VERSION').read_text()
        assert all((agents/f'uk.claimsflow.v{v}.plist.disabled').exists() for v in ('11.2','11.6','11.7','11.8','11.9','12.0'))
    else:
        with pytest.raises(RuntimeError, match='health check'):
            install.install('127.0.0.1',8767)
        assert not install.TARGET.exists()
        assert list(base.glob(f'ClaimsFlow-v{install.VERSION}.failed-*'))
        assert all((agents/f'uk.claimsflow.v{v}.plist').exists() for v in ('11.2','11.6','11.7','11.8','11.9','12.0'))
        assert any(c[:2]==('launchctl','bootstrap') and c[-1].endswith('v11.6.plist') for c in calls)
        assert any(c[:2]==('launchctl','bootstrap') and c[-1].endswith('v12.0.plist') for c in calls)
    assert (prior/'data/workbench_v7.json').read_text() == payload
    assert get_role(prior/'accounts.sqlite3', 'migration_owner') == 'admin'
    tested = next(i for i,c in enumerate(calls) if '-m' in c and 'pytest' in c)
    stopped = next(i for i,c in enumerate(calls) if c[:2]==('launchctl','bootout'))
    assert tested < stopped


def test_unknown_auth_mode_fails_closed(site, monkeypatch):
    client, _, _, _ = site
    monkeypatch.setenv('CLAIMSFLOW_AUTH_MODE','sesssions')
    assert client.get('/workbench/cases').status_code == 503
