import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
MAX_DOCUMENT_CHARS = 60000
ROUTE_OPTIONS = [
    "Fast-track",
    "Manual Review",
    "Investigation Flag",
    "Specialist Queue",
    "Standard Queue",
]

FNOL_FIELD_NAMES = [
    "policyNumber",
    "policyholderName",
    "effectiveDates",
    "incidentDate",
    "incidentTime",
    "location",
    "description",
    "claimant",
    "thirdParties",
    "contactDetails",
    "assetType",
    "assetId",
    "estimatedDamage",
    "claimType",
    "attachments",
    "initialEstimate",
]

FNOL_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        field_name: {
            "type": ["string", "null"],
            "description": f"Extracted FNOL value for {field_name}, or null if missing.",
        }
        for field_name in FNOL_FIELD_NAMES
    },
    "required": FNOL_FIELD_NAMES,
}

FNOL_ROUTING_SCHEMA = {
    "type": "object",
    "properties": {
        "route": {
            "type": "string",
            "enum": ROUTE_OPTIONS,
            "description": "The best workflow queue for this FNOL claim.",
        },
        "reasoning": {
            "type": "string",
            "description": "Brief evidence-based explanation for the selected route.",
        },
    },
    "required": ["route", "reasoning"],
}


def _load_env_file(env_path):
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        clean_line = line.strip()

        if not clean_line or clean_line.startswith("#") or "=" not in clean_line:
            continue

        key, value = clean_line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ[key] = value


def _load_local_env():
    _load_env_file(BASE_DIR.parent / ".env")
    _load_env_file(BASE_DIR / ".env")


def _get_api_key():
    _load_local_env()
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def get_gemini_model():
    _load_local_env()
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)


def is_gemini_configured():
    return bool(_get_api_key())


def get_gemini_status():
    if not is_gemini_configured():
        return {
            "configured": False,
            "model": get_gemini_model(),
            "message": "Set GEMINI_API_KEY in backend/.env or your shell.",
        }

    try:
        from google import genai  # noqa: F401
    except ImportError:
        return {
            "configured": False,
            "model": get_gemini_model(),
            "message": "Install backend requirements to enable Gemini.",
        }

    return {
        "configured": True,
        "model": get_gemini_model(),
        "message": "Gemini extraction and routing are ready.",
    }


def _empty_fields():
    return {field_name: None for field_name in FNOL_FIELD_NAMES}


def _normalize_fields(fields):
    normalized = _empty_fields()

    for field_name in FNOL_FIELD_NAMES:
        value = fields.get(field_name)

        if value is None:
            normalized[field_name] = None
            continue

        value = str(value).strip()

        if value.lower() in ["", "n/a", "na", "none", "null", "unknown"]:
            normalized[field_name] = None
        else:
            normalized[field_name] = " ".join(value.split())

    return normalized


def _merge_with_fallback(fields, fallback_fields):
    fallback_fields = fallback_fields or {}

    return {
        field_name: fields.get(field_name) or fallback_fields.get(field_name)
        for field_name in FNOL_FIELD_NAMES
    }


def _build_extraction_prompt(text):
    document_text = text[:MAX_DOCUMENT_CHARS]
    truncated_note = ""

    if len(text) > MAX_DOCUMENT_CHARS:
        truncated_note = (
            "\nThe document was truncated for model input. Extract only from the "
            "provided text and do not guess missing values."
        )

    return f"""
You are an insurance FNOL (First Notice of Loss) extraction assistant.
Extract the requested fields from the document text. The document may be an
ACORD-style Automobile Loss Notice where labels and values appear on separate
lines.

Rules:
- Return null for any field that is not explicitly present.
- Do not invent, infer, or complete missing values.
- Keep names, policy numbers, locations, dates, and descriptions faithful to the document.
- For estimatedDamage and initialEstimate, return only the numeric amount as a string.
- Normalize whitespace inside each value.

Common ACORD-style mappings:
- policyholderName may appear as "Name of Insured".
- incidentDate and incidentTime may appear together as "Date/Time of Loss".
- location may combine "Location of Loss" with "City, State, ZIP".
- description may appear as "Description of Accident"; include material damage details when helpful.
- claimant may appear as "Claim Contact Name", "Reported By", or an other-party claimant section.
- contactDetails may combine "Primary Phone" and "Primary Email".
- assetType may combine vehicle year, make, model, and body type.
- assetId may be VIN first; plate number is acceptable if VIN is absent.
- estimatedDamage and initialEstimate may appear as "Estimate Amount".
- claimType may be derived from "Line of Business" plus the loss description, for example Vehicle, Injury, Theft, Vandalism, Weather/Hail, or Property Damage.
- attachments may include police/fire department, report number, photos, remarks, or explicitly listed attachments.

Document text:
\"\"\"
{document_text}
\"\"\"
{truncated_note}
"""


def _build_routing_prompt(text, fields, missing_fields):
    document_text = text[:MAX_DOCUMENT_CHARS]
    truncated_note = ""

    if len(text) > MAX_DOCUMENT_CHARS:
        truncated_note = (
            "\nThe document was truncated for model input. Route only from the "
            "provided text and extracted fields."
        )

    return f"""
You are an insurance FNOL routing specialist.
Differentiate this claim into exactly one workflow route. The document may be
an ACORD-style Automobile Loss Notice with auto, theft, vandalism, weather,
hit-and-run, injury, and multi-vehicle/property-damage losses.

Route options:
- Investigation Flag: use when fraud, staged loss, inconsistent facts, suspicious activity, theft with suspicious facts, hit-and-run needing investigation, or material contradictions appear.
- Manual Review: use when critical information is missing or the claim cannot be confidently processed automatically.
- Specialist Queue: use for injury, bodily harm, medical treatment, complex liability, commercial auto complexity, multi-vehicle losses, or third-party property damage.
- Fast-track: use for straightforward low-complexity claims with no injuries and low estimated damage below USD 25,000, such as clean rear-end property damage, glass-only vandalism, or hail damage.
- Standard Queue: use for complete claims that do not meet fast-track, injury/specialist, manual review, or investigation criteria.

Decision requirements:
- Choose only one route from the allowed options.
- Base the decision on the document text, extracted fields, and missing fields.
- Do not route to Manual Review just because optional fields such as effective dates or attachments are absent when the ACORD form has enough claim facts to classify.
- Do not invent facts.
- Keep the reasoning concise and evidence-based.

Extracted fields:
{json.dumps(fields, indent=2)}

Missing fields:
{json.dumps(missing_fields, indent=2)}

Document text:
\"\"\"
{document_text}
\"\"\"
{truncated_note}
"""


def extract_fields_with_gemini(text, fallback_fields=None):
    fallback_fields = _normalize_fields(fallback_fields or {})
    api_key = _get_api_key()
    model = get_gemini_model()

    if not api_key:
        return fallback_fields, {
            "method": "regex",
            "usedGemini": False,
            "model": model,
            "message": "Gemini API key is not configured.",
        }

    try:
        from google import genai
    except ImportError:
        return fallback_fields, {
            "method": "regex",
            "usedGemini": False,
            "model": model,
            "message": "Gemini SDK is not installed.",
        }

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=_build_extraction_prompt(text),
            config={
                "response_mime_type": "application/json",
                "response_json_schema": FNOL_FIELD_SCHEMA,
            },
        )
        gemini_fields = _normalize_fields(json.loads(response.text))

        return _merge_with_fallback(gemini_fields, fallback_fields), {
            "method": "gemini",
            "usedGemini": True,
            "model": model,
            "message": "Gemini extracted FNOL fields.",
        }
    except Exception as error:
        return fallback_fields, {
            "method": "regex",
            "usedGemini": False,
            "model": model,
            "message": "Gemini extraction failed; used regex fallback.",
            "errorType": error.__class__.__name__,
        }


def _normalize_route(route):
    if not route:
        return None

    normalized_route = " ".join(str(route).replace("-", " ").split()).lower()
    route_aliases = {
        "fast track": "Fast-track",
        "fasttrack": "Fast-track",
        "fast track claim": "Fast-track",
        "manual review": "Manual Review",
        "investigation flag": "Investigation Flag",
        "investigation": "Investigation Flag",
        "fraud investigation": "Investigation Flag",
        "specialist queue": "Specialist Queue",
        "specialist": "Specialist Queue",
        "standard queue": "Standard Queue",
        "standard": "Standard Queue",
    }

    if route in ROUTE_OPTIONS:
        return route

    return route_aliases.get(normalized_route)


def route_claim_with_gemini(text, fields, missing_fields, fallback_result):
    api_key = _get_api_key()
    model = get_gemini_model()

    if not api_key:
        return fallback_result, {
            "method": "rules",
            "usedGemini": False,
            "model": model,
            "message": "Gemini API key is not configured.",
        }

    try:
        from google import genai
    except ImportError:
        return fallback_result, {
            "method": "rules",
            "usedGemini": False,
            "model": model,
            "message": "Gemini SDK is not installed.",
        }

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=_build_routing_prompt(text, fields, missing_fields),
            config={
                "response_mime_type": "application/json",
                "response_json_schema": FNOL_ROUTING_SCHEMA,
            },
        )
        routing_result = json.loads(response.text)
        route = _normalize_route(routing_result.get("route"))
        reasoning = str(routing_result.get("reasoning") or "").strip()

        if route is None:
            return fallback_result, {
                "method": "rules",
                "usedGemini": False,
                "model": model,
                "message": "Gemini returned an unsupported route; used rule fallback.",
            }

        return {
            "route": route,
            "reasoning": reasoning or "Gemini selected the best claim route.",
        }, {
            "method": "gemini",
            "usedGemini": True,
            "model": model,
            "message": "Gemini differentiated and routed the claim.",
        }
    except Exception as error:
        return fallback_result, {
            "method": "rules",
            "usedGemini": False,
            "model": model,
            "message": "Gemini routing failed; used rule fallback.",
            "errorType": error.__class__.__name__,
        }
