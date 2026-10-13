"""
parse_pilot.py - Parse raw JSON detail files into clean pilot_standards.json.
"""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

DETAIL_DIR = Path("raw/detail")
PILOT_JSON_PATH = Path("pilot_standards.json")

PILOT_STANDARDS = [
    "IS 15086 (Part 10):2026",
    "IS 694:2010",
    "IS 8130:2013",
    "IS 1554 (Part 1):1988",
    "IS 4289 (Part 1):2026",
    "IS 8783 (Part 4/Sec 1):2026",
    "IS 10810 (Part 60):1988",
    "IS/IEC 60136:2024",
    "IS 2026 (Part 1):2011",
    "IS 1293:2019"
]

def parse_part_section_year_prefix(std_num):
    std_num = std_num.strip()
    
    # Prefix
    if std_num.startswith("IS/IEC"):
        prefix = "IS/IEC"
    elif std_num.startswith("IS/ISO"):
        prefix = "IS/ISO"
    elif std_num.startswith("IS "):
        prefix = "IS"
    else:
        prefix = std_num.split()[0] if std_num else "IS"

    # Year
    m_year = re.search(r':(\d{4})$', std_num)
    year = int(m_year.group(1)) if m_year else None

    # Part & Section
    part = None
    section = None

    # Check for (Part X/Sec Y) or (Part X)
    m_part_sec = re.search(r'\((?:Part|Pt)\.?\s*([^/:\)]+)(?:/Sec\.?\s*([^:\)]+))?\)', std_num, re.IGNORECASE)
    if m_part_sec:
        part_val = m_part_sec.group(1).strip()
        part = f"Part {part_val}" if not part_val.lower().startswith("part") else part_val
        if m_part_sec.group(2):
            sec_val = m_part_sec.group(2).strip()
            section = f"Sec {sec_val}" if not sec_val.lower().startswith("sec") else sec_val
    else:
        # Check standalone Part
        m_part = re.search(r'\bPart\s+([0-9]+[A-Za-z]?)\b', std_num, re.IGNORECASE)
        if m_part:
            part = f"Part {m_part.group(1).strip()}"
        m_sec = re.search(r'\bSec(?:tion)?\s+([0-9]+[A-Za-z]?)\b', std_num, re.IGNORECASE)
        if m_sec:
            section = f"Sec {m_sec.group(1).strip()}"

    return prefix, part, section, year

def normalize_title(title):
    if not title:
        return None
    # Normalize multiple whitespace characters and newlines
    clean = re.sub(r'\s+', ' ', title).strip()
    # Normalize trailing and leading hyphens/artifacts
    clean = clean.replace('--', ' - ')
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def map_lifecycle_status(is_status, withdraw_status):
    if withdraw_status == 1 or withdraw_status == "1":
        return "Withdrawn"
    status_map = {
        1: "Draft / Formulation",
        2: "Current",
        3: "Under Review / Reaffirmation",
        4: "Superseded",
        5: "Withdrawn"
    }
    return status_map.get(is_status, f"Status_{is_status}" if is_status is not None else "Unknown")

def parse_int_safe(val, default=0):
    if val is None or val == "":
        return default
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return default

def parse_standard(row, fetch_time=None):
    pk_is_id = str(row["pk_is_id"]).strip()
    std_dir = DETAIL_DIR / pk_is_id

    if not std_dir.exists():
        print(f"Directory {std_dir} does not exist yet!")
        return None

    def load_json(name):
        p = std_dir / f"{name}.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    main_json = load_json("getWebsiteStandardDetails")
    cross_json = load_json("getCrossRefDetails")
    amd_json = load_json("getAmendmentDetails")
    gaz_json = load_json("getGazettedetails")
    lic_json = load_json("getStandardLicenseDetails")
    crs_json = load_json("getStandardCRSDetails")
    mcs_json = load_json("getStandardMCSDetails")
    lab_json = load_json("getStandardLaboratoryDetails")
    man_json = load_json("getProductManualDetails")
    cor_json = load_json("getCorrigendumDetails")
    sum_json = load_json("getSummaryDetails")

    d = main_json.get("data") or {}

    std_num = d.get("standardNumber") or row.get("standardNumber", "")
    prefix, part, section, year = parse_part_section_year_prefix(std_num)

    title = normalize_title(d.get("standardName") or row.get("standardName", ""))

    equivalent_std = d.get("equivalentIs") or d.get("identical_is") or None
    if equivalent_std in ["NULL", ""]:
        equivalent_std = None

    # Classification
    tc_code = None
    tc_name = d.get("committeeName")
    tc_prepared = d.get("committeePreparedName")
    if tc_prepared and " - " in tc_prepared:
        parts = tc_prepared.split(" - ", 1)
        tc_code = parts[0].strip()
        tc_name = parts[1].strip()
    elif d.get("committeeId"):
        tc_code = f"ETD {d.get('committeeId')}"

    ics = d.get("icsCode")
    ics_codes = [x.strip() for x in ics.replace("ICS", "").split(";")] if ics else []

    # Lifecycle
    life_status = map_lifecycle_status(d.get("isStatus"), d.get("withdrawStatus"))
    superseding_is = d.get("supersheed") or d.get("superseded_byis") or None
    if superseding_is in ["", "NULL"]:
        superseding_is = None

    reaff_val = d.get("reAffirmationYear")
    reaff_year = None
    if reaff_val:
        m = re.search(r'(\d{4})', str(reaff_val))
        if m:
            reaff_year = int(m.group(1))

    # Certification
    cert_type = d.get("certificationName") or None
    if cert_type in ["", "--"]:
        cert_type = None

    lic_count = lic_json.get("pagination", {}).get("totalRecord", 0)
    crs_count = crs_json.get("pagination", {}).get("totalRecord", 0)
    mcs_count = mcs_json.get("pagination", {}).get("totalRecord", 0)
    lab_count = lab_json.get("pagination", {}).get("totalRecord", 0)

    # QCO references
    qco_ref = None
    ministry = d.get("ministryName")
    if ministry and ("dpiit" in ministry.lower() or "order" in ministry.lower() or "ministry" in ministry.lower()):
        qco_ref = ministry

    # References from getCrossRefDetails
    references = []
    cross_list = cross_json.get("data", {}).get("crossRefData") if isinstance(cross_json.get("data"), dict) else cross_json.get("data")
    if isinstance(cross_list, list):
        for cr in cross_list:
            cr_num = cr.get("standardNumber", "").strip()
            cr_year = None
            if ":" in cr_num:
                m = re.search(r':(\d{4})$', cr_num)
                if m:
                    cr_year = int(m.group(1))
            references.append({
                "referred_is_number": cr_num,
                "referred_year": cr_year,
                "raw_text": normalize_title(cr.get("standardName")),
                "type_label": cr.get("typeLabel"),
                "standard_enc_id": cr.get("standardEncId")
            })

    # Amendments
    amendments = []
    amd_list = amd_json.get("data")
    if isinstance(amd_list, list):
        for amd in amd_list:
            amendments.append({
                "amendment_no": amd.get("noOfAmendment"),
                "date": amd.get("amendmentYear"),
                "raw_text": amd.get("amendmentLabel"),
                "document_path": amd.get("is_documents")
            })

    # Gazette
    gazette_entries = []
    gaz_list = gaz_json.get("data")
    if isinstance(gaz_list, list):
        for g in gaz_list:
            gazette_entries.append({
                "gazette_type": "Statutory Order / Notification",
                "notification_ref": (g.get("So_No") or "").strip(),
                "amendment_no": g.get("Amd_No"),
                "standard_number": (g.get("standardNumber") or "").strip(),
                "date": None,
                "subject": g.get("standardNumber"),
                "withdrawn_standards": None,
                "document_path": g.get("migratedFiles")
            })

    # Known mapped keys in d to exclude from raw_extra
    mapped_keys = {
        "pk_is_id", "standardNumber", "standardName", "publishedOn", "committeeId",
        "departmentId", "noOfRevision", "noOfAmendment", "typeOfStandardId",
        "degreeOfEquivalenceId", "languageId", "icsCode", "shortTitle",
        "certificationName", "equivalenceTypeName", "supersheed", "reAffirmationYear",
        "equivalenceId", "is_documents", "is_hindi_document", "equivalentIs",
        "identical_is", "reviewOn", "source", "withdrawStatus", "withdrawOn",
        "isStatus", "superseded_byis", "committeeName", "departmentName",
        "deptAliasName", "committeePreparedName", "deptPreparedName", "ministryName"
    }
    raw_extra = {k: v for k, v in d.items() if k not in mapped_keys}

    record = {
        "identity": {
            "pk_is_id": parse_int_safe(d.get("pk_is_id") or row.get("pk_is_id")),
            "is_number": std_num,
            "part": part,
            "section": section,
            "year": year,
            "prefix": prefix,
            "title": title,
            "equivalent_std": equivalent_std
        },
        "classification": {
            "department": d.get("deptPreparedName") or d.get("departmentName") or "Electrotechnical Department(ETD)",
            "technical_committee": {
                "code": tc_code,
                "name": tc_name,
                "full": tc_prepared
            },
            "ics_code(s)": ics_codes,
            "type_of_standard": d.get("typeOfStandardId"),
            "degree_of_equivalence": d.get("equivalenceTypeName"),
            "language": d.get("languageId") or "English"
        },
        "lifecycle": {
            "life_cycle_status": life_status,
            "superseding_is": superseding_is,
            "number_of_revisions": parse_int_safe(d.get("noOfRevision")),
            "number_of_amendments": parse_int_safe(d.get("noOfAmendment") or amd_json.get("totalAmendments")),
            "reaffirmation_year": reaff_year,
            "published_on": d.get("publishedOn"),
            "review_on": d.get("reviewOn")
        },
        "certification": {
            "certification_type": cert_type,
            "licence_count": lic_count,
            "CRS_data": {
                "total_records": crs_count,
                "sample": crs_json.get("data", [])[:3] if isinstance(crs_json.get("data"), list) else []
            },
            "MCS_data": {
                "total_records": mcs_count,
                "sample": mcs_json.get("data", [])[:3] if isinstance(mcs_json.get("data"), list) else []
            },
            "laboratory_count": lab_count,
            "QCO_references": qco_ref
        },
        "references": references,
        "amendments": amendments,
        "gazette": gazette_entries,
        "source": {
            "detail_url": f"https://standards.bis.gov.in/website/standard-details?encryptedId={row['standardId']}",
            "fetched_at": fetch_time or datetime.now(timezone.utc).isoformat()
        },
        "raw_extra": raw_extra
    }
    return record

def main():
    csv_path = Path("standards_list.csv")
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = {r["standardNumber"].strip(): r for r in csv.DictReader(f)}

    pilot_data = []
    print(f"Parsing {len(PILOT_STANDARDS)} pilot standards into {PILOT_JSON_PATH}...")

    for std_num in PILOT_STANDARDS:
        row = rows.get(std_num)
        if not row:
            print(f"Standard {std_num} not in CSV!")
            continue
        parsed = parse_standard(row)
        if parsed:
            pilot_data.append(parsed)
            print(f"  Parsed {std_num} -> pk_is_id={parsed['identity']['pk_is_id']}")

    PILOT_JSON_PATH.write_text(json.dumps(pilot_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(pilot_data)} standards to {PILOT_JSON_PATH}")

if __name__ == "__main__":
    main()
