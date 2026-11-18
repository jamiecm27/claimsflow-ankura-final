"""Independent synthetic claims domain model and evaluation rules."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
import random

QUEUES = ['Fast Track', 'Standard Queue', 'Specialist Queue', 'Manual Review', 'Investigation']
TYPES = ['Motor', 'Property', 'Theft', 'Injury', 'Weather']

def route_claim(claim: dict) -> tuple[str, list[str]]:
    notes = str(claim.get('description') or '').lower()
    missing = [key for key in ('policy_number', 'claim_type', 'estimated_damage') if claim.get(key) in (None, '')]
    if any(word in notes for word in ('fraud', 'forged', 'staged', 'suspicious')):
        return 'Investigation', ['Potential irregularity requires human investigation; no fraud finding is made.']
    if missing:
        return 'Manual Review', ['Missing: ' + ', '.join(missing)]
    if str(claim.get('claim_type')).lower() == 'injury':
        return 'Specialist Queue', ['Injury claim requires specialist review.']
    try:
        amount = float(claim['estimated_damage'])
    except (TypeError, ValueError):
        return 'Manual Review', ['Estimated damage is not a valid amount.']
    if amount < 25000:
        return 'Fast Track', ['Below illustrative £25,000 triage threshold.']
    return 'Standard Queue', ['Standard handling criteria apply.']

def make_claim(index: int) -> dict:
    rng = random.Random(2100 + index)
    kind = TYPES[index % len(TYPES)]
    amount = rng.choice([1200, 3600, 8900, 17000, 28000, 42000])
    claim = {
        'id': f'CLM-{index:04d}', 'policy_number': f'POL-{700000 + index}',
        'claimant': f'Synthetic Claimant {index}', 'claim_type': kind,
        'estimated_damage': amount, 'description': f'Fictional {kind.lower()} incident for prototype evaluation.',
        'status': 'New', 'created_at': datetime.now(timezone.utc).isoformat(), 'documents': [],
    }
    claim['suggested_route'], _ = route_claim(claim)
    return claim

def sample_claims(count=12):
    return [make_claim(i) for i in range(1, count + 1)]

def metrics(records: list[dict], hourly_rate=32, api_cost=0.04, human_minutes=18, ai_check_minutes=3):
    ai = [r for r in records if r.get('mode') == 'ai' and r.get('ai_provider') == 'gemini']
    manual = [r for r in records if r.get('mode') == 'manual']
    ai_ids = {r['claim_id'] for r in ai}
    paired = [r for r in manual if r['claim_id'] in ai_ids]
    def avg(values):
        return round(sum(values) / len(values), 2) if values else None
    def summary(rows, mode):
        if not rows:
            return {'count': 0, 'minutes': None, 'cost': None, 'route_agreement': None}
        minutes = [r.get('elapsed_seconds', 0) / 60 for r in rows] if mode == 'manual' else [r.get('ai_seconds', 0) / 60 + ai_check_minutes for r in rows]
        cost = [(m / 60) * hourly_rate + (api_cost if mode == 'ai' else 0) for m in minutes]
        comparisons = [r for r in rows if r.get('reference_route')]
        agreement = (sum(r.get('final_route') == r['reference_route'] for r in comparisons) / len(comparisons) * 100) if comparisons else None
        return {'count': len(rows), 'minutes': avg(minutes), 'cost': avg(cost), 'route_agreement': avg([agreement]) if agreement is not None else None}
    return {
        'ai': summary(ai, 'ai'), 'manual': summary(manual, 'manual'),
        'paired_manual': summary(paired, 'manual'),
        'simulated_human': {'count': len(ai), 'minutes': human_minutes, 'cost': round(human_minutes / 60 * hourly_rate, 2), 'route_agreement': None},
        'notes': 'Simulated human values are assumptions; AI checking time and API cost are estimates. Manual results are observed only when submitted. AI metrics exclude fallback results.'
    }
