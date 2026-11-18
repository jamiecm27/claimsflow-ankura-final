import os
from pathlib import Path
from fastapi.testclient import TestClient
from accounts import initialize, add_user

def test_session_login_and_protection(tmp_path, monkeypatch):
    db=tmp_path/'accounts.db'
    initialize(db)
    add_user(db,'owner','a-very-long-test-password','admin')
    add_user(db,'analyst','another-long-test-password','analyst')
    monkeypatch.setenv('CLAIMSFLOW_AUTH_MODE','sessions')
    monkeypatch.setenv('CLAIMSFLOW_ACCOUNTS_DB',str(db))
    monkeypatch.setenv('CLAIMSFLOW_DATA_DIR',str(tmp_path/'data'))
    from app import app
    with TestClient(app) as client:
        assert client.get('/api/claims').status_code == 401
        assert client.get('/login').status_code == 200
        assert client.post('/api/login',json={'username':'owner','password':'wrong'}).status_code == 401
        assert client.post('/api/login',json={'username':'analyst','password':'another-long-test-password'}).status_code == 200
        assert client.get('/api/me').json()['username']=='analyst'
        assert client.post('/api/admin/generate?count=1').status_code == 403
        assert client.post('/api/logout').status_code == 200
        assert client.get('/api/claims').status_code == 401
        assert client.post('/api/login',json={'username':'owner','password':'a-very-long-test-password'}).status_code == 200
        assert client.get('/api/claims').status_code == 200
        assert client.post('/api/admin/generate?count=1',headers={'Origin':'https://evil.example'}).status_code == 403
