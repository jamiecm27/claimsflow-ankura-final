def clean_amount(amount):
    if not amount:
        return None

    try:
        clean_value = (
            str(amount)
            .replace(",", "")
            .replace("$", "")
            .replace("USD", "")
            .strip()
        )
        return int(float(clean_value))
    except ValueError:
        return None


def route_claim(fields, missing_fields):
    description = fields.get("description", "") or ""
    claim_type = fields.get("claimType", "") or ""
    estimated_damage = clean_amount(fields.get("estimatedDamage"))

    fraud_keywords = ["fraud", "inconsistent", "staged"]

    if any(word in description.lower() for word in fraud_keywords):
        return {
            "route": "Investigation Flag",
            "reasoning": "Description contains fraud or inconsistency related keywords.",
        }

    if missing_fields:
        return {
            "route": "Manual Review",
            "reasoning": "One or more mandatory fields are missing.",
        }

    if claim_type.lower() == "injury":
        return {
            "route": "Specialist Queue",
            "reasoning": "Claim type is injury, so it requires specialist handling.",
        }

    if estimated_damage is not None and estimated_damage < 25000:
        return {
            "route": "Fast-track",
            "reasoning": "Estimated damage is below $25,000.",
        }

    return {
        "route": "Standard Queue",
        "reasoning": "All mandatory fields are present, but claim does not meet fast-track, injury, or investigation criteria.",
    }
