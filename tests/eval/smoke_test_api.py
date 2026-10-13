# -*- coding: utf-8 -*-
import sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

def post_json(url, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=35) as resp:
        return resp.status, json.loads(resp.read())

def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.status, json.loads(resp.read())

print('=== POST /api/recommend ===')
http_status, d = post_json('http://127.0.0.1:8000/api/recommend', {'query': 'PVC cable 1.1kV copper conductor'})
resp_status = d.get('status')
print(f'HTTP {http_status}  response.status={resp_status}')
cands = d.get('primary') or d.get('candidates') or []
for i, c in enumerate(cands[:3], 1):
    conf = c.get('confidence')
    sn = c.get('standard_number')
    title = str(c.get('title', ''))[:70]
    print(f'  {i}. [{conf}%] {sn}  {title}')
if not cands:
    print(f'  No candidates. Full response: {json.dumps(d, indent=2)[:800]}')

print()
s, d2 = get_json('http://127.0.0.1:8000/api/health')
print(f'GET /api/health: {s}  {d2}')

s, d3 = get_json('http://127.0.0.1:8000/api/audit/jobs')
print(f'GET /api/audit/jobs: {s}  {d3}')
