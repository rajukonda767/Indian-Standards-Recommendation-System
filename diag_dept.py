import requests, json, time

BASE_URL = 'https://standardsadmin.bis.gov.in/review-service//'
HEADERS = {
    'Content-Type': 'application/json',
    'Origin': 'https://standards.bis.gov.in',
    'Referer': 'https://standards.bis.gov.in/',
    'User-Agent': 'Mozilla/5.0',
}

ayd_enc = 'eyJpdiI6Ik5Sd01GNWh1cStPMEpwaWhpbVdWRGc9PSIsInZhbHVlIjoiWXRhQ29pcFdFd0pyNEtTanVSMS9KUT09IiwibWFjIjoiNjIxZDYxMjA0YWEyY2JhNDY2YTU1YjM0Y2I4ZTRiYWQ1ZDcwM2Q0ZGFjOGZhNTMxNjU0YzQ2NjFiZGUyYjA0MiIsInRhZyI6IiJ9'

def fetch(enc, offset, limit=10):
    payload = {
        'typeSelected': 7, 'encDepartmentId': enc,
        'offset': offset, 'limit': limit,
        'token': None, 'refreshToken': None,
        'clientId': None, 'clientSecret': None, 'sub': None
    }
    r = requests.post(BASE_URL + 'getWebsitePSTechDepartmentWise', json=payload, headers=HEADERS, timeout=30)
    return r.json()

print("=== AYD offset=0 ===")
d = fetch(ayd_enc, 0)
print("totalRecord:", d.get('totalRecord'))
for row in d.get('data', []):
    sn = row.get('standardNumber', '')
    dept_id = row.get('departmentId', '?')
    print(f"  {sn:<35} deptId={dept_id}")

time.sleep(1)
print("\n=== AYD offset=4000 ===")
d2 = fetch(ayd_enc, 4000)
for row in d2.get('data', []):
    sn = row.get('standardNumber', '')
    dept_id = row.get('departmentId', '?')
    print(f"  {sn:<35} deptId={dept_id}")

time.sleep(1)
ced_enc = 'eyJpdiI6IjlNTUlublg2eVNlaUt3RUxUSnRBUmc9PSIsInZhbHVlIjoic2hSZXNqRmlnTm9aK1hSejNKM2hiZz09IiwibWFjIjoiZGVmYjMxZTczYzAzN2E2NjJiYTQ2NGMyNjkwMzQzMGI4NmU0MGZkNzQxNDNiMGFmNmU3ODQ5YjJiZGM2NzcyMCIsInRhZyI6IiJ9'
print("\n=== CED offset=0 ===")
d3 = fetch(ced_enc, 0)
print("totalRecord:", d3.get('totalRecord'))
for row in d3.get('data', []):
    sn = row.get('standardNumber', '')
    dept_id = row.get('departmentId', '?')
    print(f"  {sn:<35} deptId={dept_id}")
