"""
select_400_standards.py - Selects the optimal 400 procurement standards for SIH-26108 MVP:
- 150 from CED (Civil Engineering)
- 150 from ETD (Electrotechnical)
- 100 from MTD (Metallurgical)
"""

import csv
import json
import re
from pathlib import Path

CED_CSV = Path("ced_standards_list.csv")
ETD_CSV = Path("standards_list.csv")
MTD_CSV = Path("mtd_standards_list.csv")
OUT_CSV = Path("selected_400_standards.csv")
OUT_JSON = Path("selected_400_standards.json")

# Domain keyword definitions prioritized for public and private procurement tenders
CED_KEYWORDS = [
    # Cement & Concrete
    r"\bcement\b", r"\bportland\b", r"\bconcrete\b", r"\bmix\b", r"\badmixture\b",
    # Aggregates & Sand
    r"\baggregate\b", r"\bsand\b",
    # Bricks, Blocks & Masonry
    r"\bbrick\b", r"\bblock\b", r"\baac\b", r"\bmasonry\b", r"\bpaver\b",
    # Structural & Building Materials
    r"\bplywood\b", r"\btimber\b", r"\bdoor\b", r"\bwindow\b", r"\bshutter\b",
    r"\bglass\b", r"\btile\b", r"\bceramic\b", r"\bflooring\b",
    # Pipes & Plumbing
    r"\bpipe\b", r"\btube\b", r"\bplumbing\b", r"\bsanitary\b", r"\bfitting\b",
    r"\bmanhole\b", r"\bdrainage\b", r"\bsewer\b",
    # Bitumen & Waterproofing
    r"\bbitumen\b", r"\basphalt\b", r"\bwaterproofing\b", r"\bsealant\b",
    # General Civil Procurement
    r"\breinforcement\b", r"\bstructural\b", r"\bsteel\b", r"\broof\b", r"\bpaint\b"
]

ETD_KEYWORDS = [
    # Cables & Conductors
    r"\bcable\b", r"\bwire\b", r"\bconductor\b", r"\bcord\b",
    # Switches & Accessories
    r"\bswitch\b", r"\bsocket\b", r"\bplug\b", r"\bconduit\b", r"\baccessory\b",
    # Transformers & Distribution
    r"\btransformer\b", r"\bdistribution board\b", r"\bsubstation\b",
    # Motors & Machinery
    r"\bmotor\b", r"\bgenerator\b", r"\bstarter\b",
    # Switchgear & Protection
    r"\bswitchgear\b", r"\bbreaker\b", r"\bmcb\b", r"\bmccb\b", r"\brccb\b",
    r"\bfuse\b", r"\bisolator\b", r"\brelay\b", r"\barrester\b",
    # Lighting & Lamps
    r"\blamp\b", r"\bled\b", r"\bluminaire\b", r"\blighting\b", r"\bdriver\b", r"\bballast\b",
    # Meters & Solar/Storage
    r"\bmeter\b", r"\bbattery\b", r"\binverter\b", r"\bphotovoltaic\b", r"\bsolar\b", r"\bearthing\b"
]

MTD_KEYWORDS = [
    # Reinforcement & Structural Steel
    r"\btmt\b", r"\breinforcement\b", r"\bbar\b", r"\bstructural steel\b", r"\bsection\b",
    r"\bbeam\b", r"\bcolumn\b", r"\bchannel\b", r"\bangle\b",
    # Steel Pipes & Tubes
    r"\bpipe\b", r"\btube\b", r"\bcasing\b", r"\bhollow section\b",
    # Sheets, Plates & Strips
    r"\bsheet\b", r"\bplate\b", r"\bstrip\b", r"\bgalvanized\b", r"\bgalvanised\b",
    # Welding Materials
    r"\bweld\b", r"\belectrode\b", r"\bwire rod\b", r"\bflux\b",
    # Non-ferrous Metals
    r"\baluminium\b", r"\bcopper\b", r"\bzinc\b", r"\blead\b", r"\balloy\b",
    # Testing & Mechanical Properties
    r"\btensile\b", r"\bbend\b", r"\bimpact\b", r"\bhardness\b", r"\bchemical analysis\b"
]

def calculate_score(row, keywords):
    score = 0
    title = (row.get("standardName") or "").lower()
    std_num = (row.get("standardNumber") or "").lower()
    std_type = (row.get("typeOfStandardName") or "").lower()

    # 1. Product Specification preference (+30 pts)
    if "product" in std_type or "specification" in std_type:
        score += 30
    elif "code of practice" in std_type:
        score += 20
    elif "method" in std_type:
        score += 15

    # 2. Status Preference (+25 pts for Current isStatus=2)
    status = str(row.get("isStatus", "")).strip()
    if status == "2":
        score += 25
    elif status == "1":
        score += 15  # New publications / revisions

    # 3. Revision count (+5 pts per revision, up to 20 pts)
    rev_str = str(row.get("noOfRevision", "0")).strip()
    try:
        rev_count = int(rev_str)
        score += min(rev_count * 5, 20)
    except Exception:
        pass

    # 4. Keyword Matches (+10 pts per unique matching keyword category)
    match_count = 0
    for kw in keywords:
        if re.search(kw, title) or re.search(kw, std_num):
            match_count += 1
    score += min(match_count * 10, 40)

    # 5. Recent publication (+10 pts if published after 2010)
    pub_on = row.get("publishedOn") or ""
    m = re.search(r'(20[12][0-9])', pub_on)
    if m:
        year = int(m.group(1))
        if year >= 2015:
            score += 15
        elif year >= 2010:
            score += 10

    return score

def select_for_department(csv_path, dept_code, keywords, target_count):
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # Calculate scores
    scored = []
    for r in rows:
        sc = calculate_score(r, keywords)
        r_copy = dict(r)
        r_copy["deptCode"] = dept_code
        r_copy["relevanceScore"] = sc
        scored.append(r_copy)

    # Sort descending by score, then by standard number
    scored.sort(key=lambda x: (x["relevanceScore"], x["publishedOn"] or ""), reverse=True)

    selected = scored[:target_count]
    print(f"[{dept_code}] Total available: {len(rows)} | Selected: {len(selected)} (Score range: {selected[-1]['relevanceScore']} to {selected[0]['relevanceScore']})")
    return selected

def main():
    ced_selected = select_for_department(CED_CSV, "CED", CED_KEYWORDS, 150)
    etd_selected = select_for_department(ETD_CSV, "ETD", ETD_KEYWORDS, 150)
    mtd_selected = select_for_department(MTD_CSV, "MTD", MTD_KEYWORDS, 100)

    total_400 = ced_selected + etd_selected + mtd_selected
    print(f"\nTotal Selected Standards: {len(total_400)}")

    # Verify counts
    counts = {}
    for r in total_400:
        counts[r["deptCode"]] = counts.get(r["deptCode"], 0) + 1
    print("Counts per department:", counts)

    # Save to CSV
    cols = ["deptCode", "pk_is_id", "standardNumber", "standardName", "publishedOn", 
            "isStatus", "noOfRevision", "typeOfStandardName", "relevanceScore", "standardId"]
    
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(total_400)

    # Save to JSON
    OUT_JSON.write_text(json.dumps(total_400, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(total_400)} standards to {OUT_CSV} and {OUT_JSON}")

if __name__ == "__main__":
    main()
