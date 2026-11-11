from pathlib import Path
from fastapi.testclient import TestClient
from app import app
from workbench import initial, score, case_text

client=TestClient(app)

def test_six_seeded_cases_have_multiple_pdfs():
    cases=initial()['cases']
    assert len(cases)==6
    assert all(len(c['documents'])==2 for c in cases)
    assert 'Evidence:' in case_text(cases[0])
    assert case_text(cases[0]).count('--- Evidence:')==2

def test_reference_scoring():
    assert score({},'Fast-track','CLM-001')['referenceAvailable']
    assert score({},'Fast-track','CLM-001')['routeAgreement'] is True
    assert score({},'Fast-track','CLM-UNKNOWN')['fieldAccuracy'] is None

def test_pdf_upload_and_history(tmp_path,monkeypatch):
    import workbench
    monkeypatch.setattr(workbench,'DB',tmp_path/'db.json')
    # Uploads are synthetic and temporary for this test.
    pdf=(Path(__file__).parents[1]/'sample-docs'/'CLM_001_supporting_evidence.pdf').read_bytes()
    response=client.post('/workbench/cases',data={'title':'Synthetic test'},files=[('documents',('evidence.pdf',pdf,'application/pdf'))])
    assert response.status_code==200
    case=response.json()
    assert len(case['documents'])==1
    assert client.get(f"/workbench/cases/{case['id']}/documents/{case['documents'][0]}").status_code==200
    submission=client.post('/workbench/attempts',json={'caseId':case['id'],'mode':'manual','elapsedSeconds':17,'fields':{'policyNumber':'FAKE'},'finalRoute':'Manual Review','decisionReason':'Needs evidence'})
    assert submission.status_code==200
    assert submission.json()['quality']['referenceAvailable'] is False
    history=client.get(f"/workbench/cases/{case['id']}/history").json()
    assert len(history['attempts'])==1
    assert history['attempts'][0]['humanApproved'] is True
    import shutil
    shutil.rmtree(workbench.BASE/'uploads'/case['id'],ignore_errors=True)

def test_rule_based_counterfactual_name_consistency():
    from router import route_claim
    base={'description':'Minor parking collision','claimType':'Motor','estimatedDamage':'1200','claimant':'Fictional Person A'}
    changed={**base,'claimant':'Fictional Person B'}
    assert route_claim(base,[]) == route_claim(changed,[])
    # This checks only the deterministic fallback, not Gemini fairness.
