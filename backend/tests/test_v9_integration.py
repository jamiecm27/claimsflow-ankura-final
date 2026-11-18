"""HTTP smoke tests for isolated v9 synthetic-data prototype."""
import importlib
import os
from pathlib import Path
from fastapi.testclient import TestClient
from accounts import initialize, add_user


def test_login_claims_logout(tmp_path, monkeypatch):
    db = tmp_path / 'accounts.sqlite3'
    initialize(db)
    add_user(db, 'tester', 'test-password-12345', 'admin')
    monkeypatch.setenv('CLAIMSFLOW_ACCOUNTS_DB', str(db))
    monkeypatch.setenv('CLAIMSFLOW_AUTH_MODE', 'sessions')
    monkeypatch.setenv('CLAIMSFLOW_DATA_DIR', str(tmp_path / 'data'))
    import app as app_module
    importlib.reload(app_module)
    with TestClient(app_module.app) as client:
        assert client.get('/api/claims').status_code == 401
        assert client.post('/api/login', json={'username':'tester','password':'wrong'}).status_code == 401
        assert client.post('/api/login', json={'username':'tester','password':'test-password-12345'}).status_code == 200
        assert client.get('/api/health').status_code == 200
        assert client.get('/api/claims').status_code == 200
        assert client.post('/api/logout').status_code == 200
        assert client.get('/api/claims').status_code == 401
