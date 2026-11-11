from validator import MANDATORY_FIELDS, find_missing_fields


def test_find_missing_fields_returns_empty_for_complete_claim():
    fields = {field: "present" for field in MANDATORY_FIELDS}

    assert find_missing_fields(fields) == []


def test_find_missing_fields_flags_absent_none_and_blank_values_in_schema_order():
    fields = {field: "present" for field in MANDATORY_FIELDS}
    fields["policyNumber"] = " "
    fields["incidentTime"] = None
    del fields["attachments"]

    assert find_missing_fields(fields) == [
        "policyNumber",
        "incidentTime",
        "attachments",
    ]
