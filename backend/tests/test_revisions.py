from fastapi.testclient import TestClient
from app import app
import workbench


def test_revision_preserves_original(tmp_path, monkeypatch):
    monkeypatch.setattr(workbench, 'DB', tmp_path / 'workbench.json')
    client = TestClient(app)
    case_id = client.get('/workbench/cases').json()[0]['id']
    first = client.post('/workbench/attempts', json={
        'caseId':case_id, 'mode':'manual','elapsedSeconds':120,
        'fields':{'policyNumber':'OLD'},'finalRoute':'Manual Review',
        'decisionReason':'Initial review'
    })
    assert first.status_code == 200, first.text
    old = first.json()
    revision = client.post(f'/workbench/cases/{case_id}/revisions', json={
        'basedOnAttemptId':old['id'], 'fields':{'policyNumber':'NEW'},
        'finalRoute':'Specialist Queue', 'decisionReason':'Evidence corrected'
    })
    assert revision.status_code == 200, revision.text
    history = client.get(f'/workbench/cases/{case_id}/history').json()
    assert history['attempts'][0]['fields']['policyNumber'] == 'OLD'
    assert history['attempts'][1]['fields']['policyNumber'] == 'NEW'
    assert history['attempts'][1]['basedOnAttemptId'] == old['id']
    assert history['attempts'][1]['isRevision'] is True
    assert history['case']['status'] == 'Specialist referral'
    assert client.post(f'/workbench/cases/{case_id}/revisions', json={
        'basedOnAttemptId':old['id'],'fields':{},'finalRoute':'Manual Review',
        'decisionReason':''
    }).status_code == 400
