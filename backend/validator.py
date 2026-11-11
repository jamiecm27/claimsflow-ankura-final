MANDATORY_FIELDS = [
    "policyNumber",
    "policyholderName",
    "effectiveDates",
    "incidentDate",
    "incidentTime",
    "location",
    "description",
    "claimant",
    "contactDetails",
    "assetType",
    "assetId",
    "estimatedDamage",
    "claimType",
    "attachments",
    "initialEstimate",
]


def find_missing_fields(fields):
    missing = []

    for field in MANDATORY_FIELDS:
        value = fields.get(field)

        if value is None or str(value).strip() == "":
            missing.append(field)

    return missing