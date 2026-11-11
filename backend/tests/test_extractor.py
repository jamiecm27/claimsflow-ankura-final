import pytest

from extractor import derive_claim_type, extract_fields, extract_labeled_value


def test_extract_fields_from_acord_style_multiline_text():
    text = """
    Policy Number
    POL-12345
    Name of Insured
    Avery Stone
    Policy Period
    01/01/2026 - 01/01/2027
    Date/Time of Loss
    05/12/2026 8:15 PM
    Location of Loss
    123 Market Street
    City, State, ZIP
    Boston, MA 02108
    Description of Accident
    Insured was rear-ended while stopped at a light.
    Describe Damage
    Rear bumper and trunk damage.
    Claim Contact Name
    Avery Stone
    Primary Phone
    555-0100
    Primary Email
    avery@example.com
    Line of Business
    Auto
    Year
    2022
    Make
    Toyota
    Model
    Camry
    Body Type
    Sedan
    VIN
    1HGCM82633A004352
    Estimate Amount
    $18,500.00
    Police or Fire Department
    Boston PD
    Report Number
    BPD-2026-101
    """

    assert extract_fields(text) == {
        "policyNumber": "POL-12345",
        "policyholderName": "Avery Stone",
        "effectiveDates": "01/01/2026 - 01/01/2027",
        "incidentDate": "05/12/2026",
        "incidentTime": "8:15 PM",
        "location": "123 Market Street | Boston, MA 02108",
        "description": (
            "Insured was rear-ended while stopped at a light. | "
            "Rear bumper and trunk damage."
        ),
        "claimant": "Avery Stone",
        "thirdParties": None,
        "contactDetails": "555-0100 | avery@example.com",
        "assetType": "2022 Toyota Camry Sedan",
        "assetId": "1HGCM82633A004352",
        "estimatedDamage": "18500.00",
        "claimType": "Auto",
        "attachments": "BPD-2026-101",
        "initialEstimate": "18500.00",
    }


def test_extract_labeled_value_does_not_capture_the_next_label_when_value_is_blank():
    text = """
    Policy Number
    Name of Insured
    Avery Stone
    """

    assert extract_labeled_value(["Policy Number"], text) is None
    assert extract_labeled_value(["Name of Insured"], text) == "Avery Stone"


def test_extract_fields_captures_third_party_section_until_next_section():
    text = """
    Other Vehicle / Property
    City guardrail and two parked cars damaged.
    Owner details pending.
    Reporting / Remarks
    Photos uploaded by insured.
    Description of Accident
    Driver hit a guardrail causing third-party property damage.
    Estimate Amount: USD 42,000
    """

    fields = extract_fields(text)

    assert fields["thirdParties"] == (
        "City guardrail and two parked cars damaged. Owner details pending."
    )
    assert fields["claimType"] == "Property Damage"
    assert fields["estimatedDamage"] == "42000"
    assert fields["initialEstimate"] == "42000"


@pytest.mark.parametrize(
    ("line_of_business", "description", "expected_claim_type"),
    [
        (None, "Driver reported soreness and went to urgent care.", "Injury"),
        (None, "Vehicle was stolen overnight and later recovered.", "Theft"),
        (None, "Window was shattered and the interior was rummaged.", "Vandalism"),
        (None, "Hail damaged the hood during severe weather.", "Weather/Hail"),
        ("Auto", "Rear bumper damage only.", "Auto"),
    ],
)
def test_derive_claim_type_from_loss_description(
    line_of_business,
    description,
    expected_claim_type,
):
    assert derive_claim_type(line_of_business, description) == expected_claim_type
