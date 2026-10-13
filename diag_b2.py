"""
B2 diagnostic: for standards with noOfRevision > 0 AND blank supersedes_raw,
fetch fresh from BIS API and report exact raw JSON field value.
"""

import json, pathlib, requests, time, csv, re

BASE_URL = 'https://standardsadmin.bis.gov.in/review-service//'
HEADERS = {
    'Content-Type': 'application/json',
    'Origin': 'https://standards.bis.gov.in',
    'Referer': 'https://standards.bis.gov.in/',
    'User-Agent': 'Mozilla/5.0',
}

# Find standards with revisions>0 and blank supersedes_raw in our 400
targets = []
for pk_dir in sorted(pathlib.Path('raw/detail').iterdir(), key=lambda x: int(x.name)):
    pk = pk_dir.name
    fp = pk_dir / 'getWebsiteStandardDetails.json'
    if not fp.exists():
        continue
    d = json.load(open(fp, encoding='utf-8')).get('data', {})
    rev = d.get('noOfRevision', '0') or '0'
    try:
        rev_int = int(rev)
    except:
        rev_int = 0
    sup = (d.get('supersheed') or '').strip()
    if rev_int > 0 and not sup:
        targets.append({
            'pk': pk,
            'standardNumber': d.get('standardNumber',''),
            'standardId': d.get('standardId',''),
            'noOfRevision': rev_int,
            'supersheed_cached': sup,
        })

print(f'Standards with revision>0 AND blank supersheed in cached JSON: {len(targets)}')
print()
print('Top 5 by pk:')
for t in targets[:5]:
    print(f"  pk={t['pk']} sn={t['standardNumber']} revisions={t['noOfRevision']}")

# Fetch fresh from API for 5 of them
print()
print('=== FRESH API fetch for 5 of them ===')
for t in targets[:5]:
    token = t['standardId']
    if not token:
        print(f"  {t['standardNumber']}: no token")
        continue
    
    payload = {
        'encId': token,
        'token': None, 'refreshToken': None,
        'clientId': None, 'clientSecret': None, 'sub': None
    }
    try:
        r = requests.post(BASE_URL + 'getWebsiteStandardDetails', json=payload, headers=HEADERS, timeout=20)
        d = r.json().get('data', {})
        sup_fresh = d.get('supersheed')
        print(f"  {t['standardNumber']} (pk={t['pk']}, rev={t['noOfRevision']}):")
        print(f"    supersheed (field name exact) = {repr(sup_fresh)}")
        print(f"    superseded_byis = {repr(d.get('superseded_byis'))}")
        print(f"    reviewList = {d.get('reviewList', [])[:2]}")
    except Exception as e:
        print(f"  {t['standardNumber']}: ERROR {e}")
    time.sleep(1)
