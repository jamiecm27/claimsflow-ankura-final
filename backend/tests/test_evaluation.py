from fastapi.testclient import TestClient
from app import app
import evaluation

def test_evaluation_uses_only_real_gemini_success(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluation.wb, 'DB', tmp_path/'workbench.json')
    monkeypatch.setattr(evaluation.wb, 'case_text', lambda c: 'synthetic evidence')
    monkeypatch.setattr(evaluation, 'analyze', lambda text: {'fields':{}, 'route':'Manual Review', 'extraction':'regex','routing':'rules','seconds':0.01})
    client=TestClient(app)
    result=client.post('/workbench/evaluation/run',json={'fairnessProbe':False})
    assert result.status_code==200, result.text
    report=result.json()
    assert report['summary']['totalCases']==6
    assert report['summary']['geminiSuccesses']==0
    assert report['summary']['fallbacks']==6
    assert report['summary']['fieldAccuracy'] is None
    assert len(client.get('/workbench/evaluation/runs').json())==1
    assert all(c['status']=='New' for c in client.get('/workbench/cases').json())
    assert client.get('/workbench/attempts').json()==[]
