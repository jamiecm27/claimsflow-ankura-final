import base64
from pathlib import Path
from types import SimpleNamespace
from accounts import initialize, add_user
from v9_access import authorize


def req(username=None, password=None, path='/api/claims', method='GET'):
    headers = {}
    if username is not None:
        headers['authorization'] = 'Basic ' + base64.b64encode(f'{username}:{password}'.encode()).decode()
    return SimpleNamespace(headers=headers, url=SimpleNamespace(path=path), method=method)


def test_accounts_fail_closed_without_db(monkeypatch):
    monkeypatch.delenv('CLAIMSFLOW_ACCOUNTS_DB', raising=False)
    assert authorize(req()).status_code == 503


def test_account_login_and_wrong_password(tmp_path, monkeypatch):
    db = tmp_path / 'accounts.sqlite3'
    initialize(db)
    add_user(db, 'analyst', 'long-unique-password-123')
    monkeypatch.setenv('CLAIMSFLOW_ACCOUNTS_DB', str(db))
    assert authorize(req('analyst', 'long-unique-password-123')) is None
    assert authorize(req('analyst', 'incorrect-password')).status_code == 401
    assert authorize(req()).status_code == 401


def test_restrict_administrative_changes(tmp_path, monkeypatch):
    db = tmp_path / 'accounts.sqlite3'
    initialize(db)
    add_user(db, 'analyst', 'long-unique-password-123')
    monkeypatch.setenv('CLAIMSFLOW_ACCOUNTS_DB', str(db))
    assert authorize(req('analyst', 'long-unique-password-123', '/api/admin/reset', 'POST')).status_code == 403
    assert authorize(req('analyst', 'long-unique-password-123', '/api/gemini-settings', 'POST')).status_code == 403
    assert authorize(req('analyst', 'long-unique-password-123', '/api/claims', 'POST')) is None
