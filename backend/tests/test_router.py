import pytest

from router import clean_amount, route_claim
from validator import MANDATORY_FIELDS


def complete_fields(**overrides):
    fields = {field: "present" for field in MANDATORY_FIELDS}
    fields.update(
        {
            "description": "Straightforward rear bumper damage.",
            "estimatedDamage": "18000",
            "claimType": "Auto",
        }
    )
    fields.update(overrides)
    return fields


@pytest.mark.parametrize(
    ("raw_amount", "expected"),
    [
        ("$24,999.50", 24999),
        ("USD 25,000", 25000),
        ("  18000  ", 18000),
        ("not available", None),
        (None, None),
    ],
)
def test_clean_amount_normalizes_common_currency_formats(raw_amount, expected):
    assert clean_amount(raw_amount) == expected


def test_route_claim_prioritizes_investigation_even_when_fields_are_missing():
    fields = complete_fields(description="The facts are inconsistent and may be staged.")

    result = route_claim(fields, missing_fields=["policyNumber"])

    assert result["route"] == "Investigation Flag"
    assert "fraud or inconsistency" in result["reasoning"]


def test_route_claim_sends_missing_required_data_to_manual_review_before_injury():
    fields = complete_fields(claimType="Injury", estimatedDamage="12000")

    result = route_claim(fields, missing_fields=["incidentTime"])

    assert result["route"] == "Manual Review"
    assert "mandatory fields" in result["reasoning"]


def test_route_claim_sends_injury_claims_to_specialist_queue():
    fields = complete_fields(claimType="Injury", estimatedDamage="12000")

    result = route_claim(fields, missing_fields=[])

    assert result["route"] == "Specialist Queue"
    assert "specialist" in result["reasoning"]


@pytest.mark.parametrize(
    ("estimated_damage", "expected_route"),
    [
        ("24999", "Fast-track"),
        ("25000", "Standard Queue"),
        ("not available", "Standard Queue"),
    ],
)
def test_route_claim_uses_damage_threshold_for_non_injury_claims(
    estimated_damage,
    expected_route,
):
    fields = complete_fields(estimatedDamage=estimated_damage)

    assert route_claim(fields, missing_fields=[])["route"] == expected_route
