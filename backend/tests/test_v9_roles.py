import sqlite3
import pytest
from accounts import initialize, add_user, get_role, set_role
from test_v9_access import req
from v9_access import authorize

def test_admin_and_analyst_permissions(tmp_path, monkeypatch):
    db = tmp_path/'accounts.db'; initialize(db)
    add_user(db,'owner','owner-password-long',role='admin')
    add_user(db,'analyst','analyst-password-long')
    monkeypatch.setenv('CLAIMSFLOW_ACCOUNTS_DB',str(db))
    assert authorize(req('owner','owner-password-long','/api/settings','POST')) is None
    assert authorize(req('analyst','analyst-password-long','/api/settings','POST')).status_code == 403
    assert authorize(req('analyst','analyst-password-long','/api/claims','POST')) is None
    assert get_role(db,'analyst') == 'analyst'

def test_existing_database_migrates_without_admin_escalation(tmp_path):
    db=tmp_path/'old.db'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE users (username TEXT PRIMARY KEY, salt BLOB NOT NULL, password_hash BLOB NOT NULL, active INTEGER NOT NULL DEFAULT 1)')
    initialize(db)
    add_user(db,'analyst','long-enough-password')
    assert get_role(db,'analyst') == 'analyst'

def test_last_admin_cannot_be_demoted(tmp_path):
    db=tmp_path/'accounts.db'; initialize(db)
    add_user(db,'owner','owner-password-long',role='admin')
    with pytest.raises(ValueError): set_role(db,'owner','analyst')
    add_user(db,'second','second-password-long',role='admin')
    set_role(db,'owner','analyst')
    assert get_role(db,'owner') == 'analyst'

def test_invalid_roles_rejected(tmp_path):
    db=tmp_path/'accounts.db'; initialize(db)
    with pytest.raises(ValueError): add_user(db,'x','long-enough-password',role='superuser')
