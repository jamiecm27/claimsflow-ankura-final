"""Gemini JSON analysis adapter. No silent AI-success fallback."""
import json
import os
import time
from pathlib import Path
from google.genai import types
from core import route_claim
from keychain_store import get_gemini_key


CLAIM_FORM_FIELDS = (
    'policyNumber', 'policyholderName', 'effectiveDates', 'incidentDate',
    'incidentTime', 'location', 'description', 'claimant', 'thirdParties',
    'contactDetails', 'assetType', 'assetId', 'estimatedDamage', 'claimType',
    'attachments', 'initialEstimate',
)
CLAIM_ROUTES = ('Fast Track', 'Standard Queue', 'Specialist Queue', 'Manual Review', 'Investigation')
CLAIM_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'route': {'type': 'string', 'enum': list(CLAIM_ROUTES)},
        'reason': {'type': 'string'},
        'fields': {
            'type': 'object',
            'properties': {key: {'type': ['string', 'null']} for key in CLAIM_FORM_FIELDS},
            'required': list(CLAIM_FORM_FIELDS),
        },
    },
    'required': ['route', 'reason', 'fields'],
}


def safe_error(exc):
    """Expose useful diagnostics without leaking API credentials or prompts."""
    import re
    message = str(exc)
    message = re.sub(r'AIza[0-9A-Za-z_-]+', '[REDACTED KEY]', message)
    message = re.sub(r'(?i)(key=|api[_-]?key[=: ]+)[^\s&,]+', r'\1[REDACTED]', message)
    message = message[:700]
    return f'{type(exc).__name__}: {message}'


# Prefer a user-selected model, then current Flash models. A candidate must
# successfully answer a real request before it becomes the active model.
_active_model = None
_active_key_fingerprint = None


def _candidates(client):
    preferred = os.environ.get('GEMINI_MODEL', '').strip().removeprefix('models/')
    discovered = []
    try:
        for item in client.models.list():
            actions = getattr(item, 'supported_actions', None) or getattr(item, 'supported_generation_methods', None) or []
            name = (getattr(item, 'name', '') or '').removeprefix('models/')
            if name and 'flash' in name and (not actions or 'generateContent' in actions):
                discovered.append(name)
    except Exception:
        # A failed list call must not prevent testing known candidate names.
        pass
    def priority(name):
        return (0 if name == preferred and preferred else
                1 if name.startswith('gemini-3.8-flash') else
                2 if name.startswith('gemini-3') and 'flash' in name else
                3 if name.startswith('gemini-2.5-flash') else
                4 if 'flash' in name else 5, name)
    known = ['gemini-3.8-flash', 'gemini-3-flash-preview', 'gemini-2.5-flash']
    return list(dict.fromkeys(([preferred] if preferred else []) + sorted(discovered, key=priority) + known))


def _resolve(client, key, force=False):
    global _active_model, _active_key_fingerprint
    import hashlib
    fingerprint = hashlib.sha256(key.encode()).hexdigest()
    if not force and _active_model and fingerprint == _active_key_fingerprint:
        return _active_model
    failures = []
    for model in _candidates(client)[:5]:
        try:
            response = client.models.generate_content(model=model, contents='Reply with the single word READY.')
            if (response.text or '').strip():
                _active_model, _active_key_fingerprint = model, fingerprint
                return model
            failures.append(f'{model}: empty response')
        except Exception as exc:
            failures.append(f'{model}: {safe_error(exc)}')
            # Authentication, billing, or quota problems cannot be fixed by
            # selecting another model; report the error promptly.
            status = str(exc)
            if any(token in status for token in ('401 UNAUTHENTICATED', '403 PERMISSION_DENIED', '429 RESOURCE_EXHAUSTED')):
                break
    raise RuntimeError('No usable Gemini model found. ' + ' | '.join(failures[:5]))


def active_model():
    return _active_model or 'auto (discover on first request)'


def test_connection():
    key = get_gemini_key()
    if not key:
        return {'ok': False, 'stage': 'keychain', 'model': active_model(), 'message': 'No Gemini key was found in macOS Keychain.'}
    try:
        from google import genai
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60000))
        model = _resolve(client, key, force=True)
        return {'ok': True, 'stage': 'complete', 'model': model, 'message': 'Gemini responded successfully. This model will be used for claims.'}
    except Exception as exc:
        return {'ok': False, 'stage': 'model_discovery', 'model': active_model(), 'message': safe_error(exc)}


def analyze(claim):
    started = time.monotonic()
    key = get_gemini_key()
    if not key:
        queue, reasons = route_claim(claim)
        return {'provider': 'rules_fallback', 'route': queue, 'reason': '; '.join(reasons), 'fields': {}, 'elapsed_seconds': round(time.monotonic()-started, 3), 'warning': 'No Gemini API key configured. This is NOT an AI result.'}
    try:
        from google import genai
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60000))
        contents = []
        evidence = Path(os.environ.get('CLAIMSFLOW_DATA_DIR', str(Path(__file__).parent/'data'))) / 'evidence'
        for filename in claim.get('documents', []):
            target = (evidence / claim['id'] / filename).resolve()
            if not target.is_relative_to(evidence.resolve()) or not target.is_file():
                raise ValueError('Evidence PDF is missing or outside the evidence folder')
            if target.stat().st_size > 8*1024*1024 or len(contents)>=8:
                raise ValueError('Evidence exceeds 8 PDFs or 8 MB per PDF')
            contents.append(types.Part.from_bytes(data=target.read_bytes(), mime_type='application/pdf'))
        prompt = ('You are assisting a fictional insurance triage exercise. Do not make coverage, payment, or fraud determinations. '
                  'Extract individual claim form values from the attached evidence. '
                  'Use null when the evidence does not provide a value. Treat claim metadata as context. '
                  'Flag uncertainty; do not invent missing data. Claim JSON:\n' + json.dumps(claim))
        contents.append(prompt)
        model = _resolve(client, key)
        config = types.GenerateContentConfig(
            response_mime_type='application/json',
            response_json_schema=CLAIM_RESPONSE_SCHEMA,
        )
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
        except Exception as exc:
            if '404' not in str(exc) and 'NOT_FOUND' not in str(exc):
                raise
            model = _resolve(client, key, force=True)
            response = client.models.generate_content(model=model, contents=contents, config=config)
        raw = response.text.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        result = json.loads(raw)
        if result.get('route') not in CLAIM_ROUTES:
            raise ValueError('Unexpected routing label')
        fields = result.get('fields', {})
        if not isinstance(fields, dict) or any(not isinstance(v, (str, int, float, type(None))) for v in fields.values()):
            raise ValueError('Unexpected extraction field format')
        return {'provider': 'gemini', 'route': result['route'], 'reason': str(result.get('reason', '')), 'fields': result.get('fields', {}), 'elapsed_seconds': round(time.monotonic()-started, 3), 'warning': None}
    except Exception as exc:
        queue, reasons = route_claim(claim)
        return {'provider': 'rules_fallback', 'route': queue, 'reason': '; '.join(reasons), 'fields': {}, 'elapsed_seconds': round(time.monotonic()-started, 3), 'warning': f'Gemini request failed: {safe_error(exc)}. Rules fallback only.'}
