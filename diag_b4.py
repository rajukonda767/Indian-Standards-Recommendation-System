import requests, json, csv, pathlib, re, time

BASE_URL = 'https://standardsadmin.bis.gov.in/review-service//'
HEADERS = {
    'Content-Type': 'application/json',
    'Origin': 'https://standards.bis.gov.in',
    'Referer': 'https://standards.bis.gov.in/',
    'User-Agent': 'Mozilla/5.0',
}

# Find pre-2000 standards with isStatus=1 in all_standards_index.csv
# that are also in our crawled 400
crawled_pks = set()
for d in pathlib.Path('raw/detail').iterdir():
    crawled_pks.add(d.name)

old_status1 = []
with open('all_standards_index.csv', newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        yr = r.get('year','').strip()
        st = r.get('isStatus','').strip()
        pk = r.get('pk_is_id','').strip()
        if st == '1' and yr and int(yr) < 2000 and pk in crawled_pks:
            old_status1.append(r)

print(f'Pre-2000 isStatus=1 standards in our crawled 400: {len(old_status1)}')
for r in old_status1[:10]:
    print(f"  pk={r['pk_is_id']} sn={r['standardNumber']} year={r['year']}")

# For each, check raw JSON - what does it say?
print()
print('=== Raw JSON fields for pre-2000 isStatus=1 standards ===')
for r in old_status1[:5]:
    pk = r['pk_is_id']
    fp = pathlib.Path(f'raw/detail/{pk}/getWebsiteStandardDetails.json')
    if fp.exists():
        d = json.load(open(fp, encoding='utf-8'))['data']
        print(f"  {r['standardNumber']}:")
        print(f"    isStatus={d.get('isStatus')} withdrawStatus={d.get('withdrawStatus')}")
        print(f"    publishedOn={d.get('publishedOn')} reAffirmationYear={d.get('reAffirmationYear')}")
        print(f"    superseded_byis={repr(d.get('superseded_byis'))}")
        rl = d.get('reviewList', [])
        if rl:
            print(f"    reviewList: {rl[:3]}")
        print(f"    projectStageName={repr(d.get('projectStageName'))}")

# Now fetch fresh from API for 2 specific pre-2000 standards to see current state
# IS 3574 (Part 1):1965 and IS 6491:1972 - find their standardId tokens
print()
print('=== API check for specific old standards ===')
for target in ['IS 3574 (Part 1):1965', 'IS 6491:1972', 'IS 1566:1982', 'IS 12594:1988']:
    # Find in index
    token = None
    with open('all_standards_index.csv', newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['standardNumber'].strip() == target:
                token = r['standardId']
                break
    if not token:
        print(f'  {target}: NOT IN INDEX')
        continue
    if not token.strip():
        print(f'  {target}: token empty')
        continue
    
    # Fetch fresh detail
    payload = {
        'encId': token,
        'token': None, 'refreshToken': None,
        'clientId': None, 'clientSecret': None, 'sub': None
    }
    try:
        r = requests.post(BASE_URL + 'getWebsiteStandardDetails', json=payload, headers=HEADERS, timeout=20)
        d = r.json().get('data') or {}
        print(f'  {target}:')
        print(f'    isStatus={d.get("isStatus")} withdrawStatus={d.get("withdrawStatus")}')
        print(f'    projectStageName={repr(d.get("projectStageName"))}')
        rl = d.get('reviewList', [])
        print(f'    reviewList (first 2): {rl[:2]}')
        print(f'    noOfRevision={d.get("noOfRevision")} reAffirmationYear={d.get("reAffirmationYear")}')
    except Exception as e:
        print(f'  {target}: ERROR {e}')
    time.sleep(1)
