"""
Revised Task 1: Crawl ALL standards using encDepartmentId=None (returns all 23,918),
then enrich with department info from:
  - CED/MTD/ETD CSVs (already have pk_is_id and can map)
  - For standards in our raw/detail/: use deptAliasName from getWebsiteStandardDetails
  - For rest: department=UNKNOWN (acceptable — full dept attribution would need 17 separate tokens)

Also tries each known-good dept token to verify if they filter correctly.
"""

import requests, csv, json, time, re, os, pathlib, sys

WD = pathlib.Path(".")
BASE_URL = "https://standardsadmin.bis.gov.in/review-service//"
ENDPOINT = "getWebsitePSTechDepartmentWise"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://standards.bis.gov.in",
    "Referer": "https://standards.bis.gov.in/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

OUT_FILE = "all_standards_index.csv"
PROGRESS_FILE = "task1_v2_progress.json"

COLUMNS = ["pk_is_id", "standardNumber", "base_number", "year",
           "standardName", "isStatus", "noOfRevision",
           "typeOfStandardName", "equivalenceTypeName",
           "department", "standardId"]

# Known-good department-specific tokens (verified: CED=1939, MTD=1700, ETD=1946)
KNOWN_DEPT_TOKENS = {
    "CED": "eyJpdiI6IjlNTUlublg2eVNlaUt3RUxUSnRBUmc9PSIsInZhbHVlIjoic2hSZXNqRmlnTm9aK1hSejNKM2hiZz09IiwibWFjIjoiZGVmYjMxZTczYzAzN2E2NjJiYTQ2NGMyNjkwMzQzMGI4NmU0MGZkNzQxNDNiMGFmNmU3ODQ5YjJiZGM2NzcyMCIsInRhZyI6IiJ9",
    "MTD": "eyJpdiI6InEyMFhZQVFnSDB2ZkVHd3Z6YXNINnc9PSIsInZhbHVlIjoiR0k4N0FvSDdKbFg0clVQSG9oL1lwZz09IiwibWFjIjoiZDU0ZWY3MGEwNDU5MTRiYTg4OGVhYzA1MTgxNTkyZjhkYzBhMDc4YjkyNzExZjk2ZDQzZDQzMTYxYjUwMmQyYSIsInRhZyI6IiJ9",
    "ETD": "eyJpdiI6ImJVb0FWOXNKazBEMldDa3ZXSXNlZHc9PSIsInZhbHVlIjoiQ0orb0RqMnNJTHRKY3RGRWVWakZPdz09IiwibWFjIjoiZDU0ZGEwNzRhYzk2OTMyMmQxMGMwNjZlNjI1ZjliZmUzN2IwYTI0YTViZTBhNjVjMmMwZWI1MWM2OTY3MDUwYyIsInRhZyI6IiJ9",
}


def parse_base_and_year(std_num: str):
    if not std_num:
        return "", None
    yr_match = re.search(r':(\d{4})', std_num)
    year = int(yr_match.group(1)) if yr_match else None
    base = re.sub(r'\s*:.*$', '', std_num)
    base = base.replace(' ', '').replace('(', '').replace(')', '').replace('/', '')
    return base, year


def fetch_page(enc_id, offset, limit=100):
    payload = {
        "typeSelected": 7,
        "encDepartmentId": enc_id,
        "offset": offset,
        "limit": limit,
        "token": None, "refreshToken": None,
        "clientId": None, "clientSecret": None, "sub": None,
    }
    resp = requests.post(BASE_URL + ENDPOINT, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_pk_to_dept():
    """Build mapping from pk_is_id → dept code using known-good dept CSVs + raw detail."""
    pk_dept = {}
    
    # From existing dept-specific CSVs
    for code, fname in [("CED", "ced_standards_list.csv"),
                         ("MTD", "mtd_standards_list.csv"),
                         ("ETD", "standards_list.csv")]:
        fp = WD / fname
        if fp.exists():
            with open(fp, newline='', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    pk = row.get('pk_is_id', '')
                    if pk:
                        pk_dept[pk] = code
            print(f"  Loaded {code} CSV: {sum(1 for v in pk_dept.values() if v==code)} rows")
    
    # From raw detail files
    raw_dir = WD / "raw" / "detail"
    if raw_dir.exists():
        for pk_dir in raw_dir.iterdir():
            pk = pk_dir.name
            fp = pk_dir / "getWebsiteStandardDetails.json"
            if fp.exists() and pk not in pk_dept:
                try:
                    d = json.load(open(fp, encoding='utf-8')).get('data', {})
                    dept = d.get('deptAliasName', '')
                    if dept:
                        pk_dept[pk] = dept
                except Exception:
                    pass
    
    print(f"pk_dept map: {len(pk_dept)} entries")
    return pk_dept


def main():
    print("Building pk -> department mapping...")
    pk_dept = build_pk_to_dept()
    
    # Load progress
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        progress = json.load(open(PROGRESS_FILE))
        print(f"Resuming from offset={progress.get('offset', 0)}")
    
    offset_start = progress.get('offset', 0)
    written = progress.get('written', 0)
    
    # Load existing PKs to avoid duplicates on resume
    existing_pks = set()
    if os.path.exists(OUT_FILE) and offset_start > 0:
        with open(OUT_FILE, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                existing_pks.add(row['pk_is_id'])
        print(f"Resuming: {len(existing_pks)} rows already in {OUT_FILE}")
    
    csv_mode = 'a' if offset_start > 0 else 'w'
    write_header = (offset_start == 0)
    
    with open(OUT_FILE, csv_mode, newline='', encoding='utf-8') as fout:
        writer = csv.DictWriter(fout, fieldnames=COLUMNS)
        if write_header:
            writer.writeheader()
        
        offset = offset_start
        total_record = 23918  # known from API
        
        print(f"\nCrawling all {total_record} standards (encDepartmentId=None)...")
        
        while True:
            try:
                resp = fetch_page(None, offset, 100)
            except Exception as e:
                print(f"ERROR at offset {offset}: {e}")
                progress = {'offset': offset, 'written': written}
                json.dump(progress, open(PROGRESS_FILE, 'w'))
                sys.exit(1)
            
            rows = resp.get('data') or []
            if not rows:
                print(f"No more rows at offset={offset}")
                break
            
            for row in rows:
                pk = str(row.get('pk_is_id', ''))
                if pk in existing_pks:
                    continue
                existing_pks.add(pk)
                
                std_num = (row.get('standardNumber') or '').strip()
                base, year = parse_base_and_year(std_num)
                dept = pk_dept.get(pk, 'UNKNOWN')
                
                writer.writerow({
                    'pk_is_id': pk,
                    'standardNumber': std_num,
                    'base_number': base,
                    'year': year if year else '',
                    'standardName': (row.get('standardName') or '').strip(),
                    'isStatus': row.get('isStatus', ''),
                    'noOfRevision': row.get('noOfRevision', ''),
                    'typeOfStandardName': (row.get('typeOfStandardName') or '').strip(),
                    'equivalenceTypeName': (row.get('equivalenceTypeName') or '').strip(),
                    'department': dept,
                    'standardId': (row.get('standardId') or '').strip(),
                })
                written += 1
            
            fout.flush()
            offset += len(rows)
            progress = {'offset': offset, 'written': written}
            json.dump(progress, open(PROGRESS_FILE, 'w'))
            
            print(f"  offset={offset} / {total_record}  written={written}", flush=True)
            
            if len(rows) < 100:
                break
            
            time.sleep(1)
    
    # Final count
    with open(OUT_FILE, newline='', encoding='utf-8') as f:
        total_final = sum(1 for _ in f) - 1
    
    # Department coverage
    dept_counts = {}
    with open(OUT_FILE, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            d = row.get('department', 'UNKNOWN')
            dept_counts[d] = dept_counts.get(d, 0) + 1
    
    print(f"\n{'='*60}")
    print(f"all_standards_index.csv: {total_final} rows")
    print(f"Expected: ~23,918 | Difference: {total_final - 23918:+d}")
    print("\nDepartment distribution:")
    for d, cnt in sorted(dept_counts.items(), key=lambda x: -x[1]):
        print(f"  {d:10}: {cnt}")
    print("Task 1 COMPLETE.")


if __name__ == "__main__":
    main()
