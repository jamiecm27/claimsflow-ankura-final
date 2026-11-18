import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import route_claim, sample_claims, metrics

def test_routes():
    assert route_claim({'policy_number': 'P1', 'claim_type': 'Motor', 'estimated_damage': 200})[0] == 'Fast Track'
    assert route_claim({'policy_number': 'P1', 'claim_type': 'Injury', 'estimated_damage': 200})[0] == 'Specialist Queue'
    assert route_claim({'policy_number': 'P1', 'claim_type': 'Motor', 'estimated_damage': 200, 'description': 'staged event'})[0] == 'Investigation'
    assert route_claim({'policy_number': '', 'claim_type': 'Motor', 'estimated_damage': 200})[0] == 'Manual Review'

def test_samples_are_deterministic():
    assert sample_claims(2)[0]['id'] == 'CLM-0001'
    assert sample_claims(2)[0]['estimated_damage'] == sample_claims(2)[0]['estimated_damage']

def test_empty_metrics_are_not_fabricated():
    output = metrics([])
    assert output['manual']['minutes'] is None
    assert output['ai']['route_agreement'] is None
