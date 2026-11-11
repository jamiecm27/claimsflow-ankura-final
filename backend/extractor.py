import re

import fitz


FIELD_ALIASES = {
    "policyNumber": ["Policy Number"],
    "policyholderName": ["Policyholder Name", "Name of Insured"],
    "effectiveDates": ["Effective Dates", "Policy Period", "Policy Effective Dates"],
    "incidentDate": ["Incident Date"],
    "incidentTime": ["Incident Time"],
    "location": ["Location", "Location of Loss"],
    "description": ["Description", "Description of Accident"],
    "claimant": ["Claimant", "Claim Contact Name", "Reported By"],
    "thirdParties": ["Third Parties", "Other Vehicle / Property"],
    "contactDetails": ["Contact Details"],
    "assetType": ["Asset Type"],
    "assetId": ["Asset ID", "VIN"],
    "estimatedDamage": ["Estimated Damage", "Estimate Amount"],
    "claimType": ["Claim Type"],
    "attachments": ["Attachments", "Report Number"],
    "initialEstimate": ["Initial Estimate", "Estimate Amount"],
}

FORM_LABELS = {
    "Agency",
    "Agency Address",
    "Agency Code",
    "Agency Contact",
    "Agency Customer ID",
    "Agency Email",
    "Agency Fax",
    "Agency Name",
    "Agency Phone",
    "Asset ID",
    "Asset Type",
    "Attachments",
    "Body Type",
    "Carrier",
    "Child Passenger Restraint Questions",
    "Claim Contact Address",
    "Claim Contact Name",
    "Claim Header",
    "Claim Type",
    "Contact Details",
    "Country",
    "City, State, ZIP",
    "Date Prepared",
    "Date of Birth / FEIN",
    "Date/Time of Loss",
    "Describe Damage",
    "Description",
    "Description of Accident",
    "Driver License Number",
    "Driver Name and Address",
    "Effective Dates",
    "Estimate Amount",
    "Initial Estimate",
    "Insured / Contact",
    "Insured Mailing Address",
    "Insured Vehicle",
    "Line of Business",
    "Location",
    "Location of Loss",
    "Loss Details",
    "Make",
    "Marital Status",
    "Model",
    "NAIC Code",
    "Name of Insured",
    "Other Insurance Carrier",
    "Other Insurance Policy Number",
    "Other Vehicle / Property",
    "Owner Name and Address",
    "Plate Number",
    "Plate State",
    "Police or Fire Department",
    "Policy Effective Dates",
    "Policy Number",
    "Policy Period",
    "Primary Email",
    "Primary Phone",
    "Purpose of Use",
    "Relation to Insured",
    "Remarks",
    "Report Number",
    "Reported By",
    "Reported To",
    "Reporting / Remarks",
    "Subcode",
    "Third Parties",
    "Used With Permission",
    "Vehicle Number",
    "VIN",
    "When Can Vehicle Be Seen",
    "When to Contact",
    "Where Can Vehicle Be Seen",
    "Year",
}

def extract_text_from_pdf(file_path):
    text = ""
    doc = fitz.open(file_path)

    for page in doc:
        text += page.get_text()

    return text


def extract_text_from_txt(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def extract_field(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def normalize_label(label):
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


KNOWN_LABELS = {
    normalize_label(label)
    for labels in list(FIELD_ALIASES.values()) + [list(FORM_LABELS)]
    for label in labels
}


def get_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def is_known_label(line):
    return normalize_label(line) in KNOWN_LABELS


def collect_continued_value(lines, value_start_index):
    value_lines = []

    for line in lines[value_start_index:]:
        if is_known_label(line):
            break

        value_lines.append(line)

    return " ".join(value_lines).strip() or None


def extract_labeled_value(labels, text):
    for label in labels:
        pattern = rf"{re.escape(label)}[:\-]\s*(.+)"
        value = extract_field(pattern, text)

        if value:
            return value

    lines = get_lines(text)
    normalized_labels = {normalize_label(label) for label in labels}

    for index, line in enumerate(lines[:-1]):
        if normalize_label(line) in normalized_labels:
            return collect_continued_value(lines, index + 1)

    return None


def extract_section(section_label, text):
    lines = get_lines(text)
    section_index = None
    stop_labels = {
        "agency",
        "insured contact",
        "loss details",
        "insured vehicle",
        "other vehicle property",
        "reporting remarks",
        "remarks",
    }

    for index, line in enumerate(lines):
        if normalize_label(line) == normalize_label(section_label):
            section_index = index + 1
            break

    if section_index is None:
        return None

    section_lines = []

    for line in lines[section_index:]:
        if normalize_label(line) in stop_labels and section_lines:
            break

        section_lines.append(line)

    return " ".join(section_lines).strip() or None


def split_date_time(value):
    if not value:
        return None, None

    match = re.match(r"(.+?)\s+([0-9]{1,2}:[0-9]{2}\s*(?:AM|PM)?)$", value, re.IGNORECASE)

    if not match:
        return value, None

    return match.group(1).strip(), match.group(2).strip()


def clean_money(value):
    if not value:
        return None

    match = re.search(r"([0-9][0-9,]*(?:\.[0-9]{2})?)", value)
    return match.group(1).replace(",", "") if match else None


def combine_values(*values):
    clean_values = [value for value in values if value]
    return " | ".join(clean_values) if clean_values else None


def derive_claim_type(line_of_business, description):
    combined = f"{line_of_business or ''} {description or ''}".lower()

    injury_terms = ["soreness", "urgent care", "medical", "hospital", "bodily", "injured"]

    if any(word in combined for word in injury_terms):
        return "Injury"

    if "theft" in combined or "stolen" in combined:
        return "Theft"

    if "vandal" in combined or "shattered" in combined or "rummaged" in combined:
        return "Vandalism"

    if "hail" in combined or "weather" in combined:
        return "Weather/Hail"

    if "property damage" in combined or "guardrail" in combined:
        return "Property Damage"

    if line_of_business:
        return line_of_business

    return None


def extract_vehicle_type(text):
    year = extract_labeled_value(["Year"], text)
    make = extract_labeled_value(["Make"], text)
    model = extract_labeled_value(["Model"], text)
    body_type = extract_labeled_value(["Body Type"], text)
    vehicle_parts = [part for part in [year, make, model, body_type] if part]

    return " ".join(vehicle_parts) if vehicle_parts else None


def extract_fields(text):
    date_time_of_loss = extract_labeled_value(["Date/Time of Loss"], text)
    loss_date, loss_time = split_date_time(date_time_of_loss)
    location = extract_labeled_value(["Location", "Location of Loss"], text)
    city_state_zip = extract_labeled_value(["City, State, ZIP"], text)
    description = extract_labeled_value(["Description", "Description of Accident"], text)
    damage_description = extract_labeled_value(["Describe Damage"], text)
    line_of_business = extract_labeled_value(["Line of Business"], text)
    phone = extract_labeled_value(["Primary Phone"], text)
    email = extract_labeled_value(["Primary Email"], text)
    report_number = extract_labeled_value(["Report Number"], text)
    police_or_fire = extract_labeled_value(["Police or Fire Department"], text)

    return {
        "policyNumber": extract_labeled_value(FIELD_ALIASES["policyNumber"], text),
        "policyholderName": extract_labeled_value(FIELD_ALIASES["policyholderName"], text),
        "effectiveDates": extract_labeled_value(FIELD_ALIASES["effectiveDates"], text),

        "incidentDate": extract_labeled_value(FIELD_ALIASES["incidentDate"], text) or loss_date,
        "incidentTime": extract_labeled_value(FIELD_ALIASES["incidentTime"], text) or loss_time,
        "location": combine_values(location, city_state_zip),
        "description": combine_values(description, damage_description),

        "claimant": extract_labeled_value(FIELD_ALIASES["claimant"], text),
        "thirdParties": extract_labeled_value(FIELD_ALIASES["thirdParties"], text)
        or extract_section("Other Vehicle / Property", text),
        "contactDetails": extract_labeled_value(FIELD_ALIASES["contactDetails"], text)
        or combine_values(phone, email),

        "assetType": extract_labeled_value(FIELD_ALIASES["assetType"], text)
        or extract_vehicle_type(text),
        "assetId": extract_labeled_value(FIELD_ALIASES["assetId"], text)
        or extract_labeled_value(["Plate Number"], text),
        "estimatedDamage": clean_money(
            extract_labeled_value(FIELD_ALIASES["estimatedDamage"], text)
        ),

        "claimType": extract_labeled_value(FIELD_ALIASES["claimType"], text)
        or derive_claim_type(line_of_business, combine_values(description, damage_description)),
        "attachments": extract_labeled_value(FIELD_ALIASES["attachments"], text)
        or combine_values(police_or_fire, report_number),
        "initialEstimate": clean_money(
            extract_labeled_value(FIELD_ALIASES["initialEstimate"], text)
        ),
    }
