# -*- coding: utf-8 -*-
"""Get real registered routes via OpenAPI schema (ground truth)."""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
r = client.get('/openapi.json')
spec = r.json()

print("=== ALL REGISTERED ROUTES (from OpenAPI spec) ===")
paths = spec.get('paths', {})
for path, methods_dict in sorted(paths.items()):
    for method in sorted(methods_dict.keys()):
        tags = methods_dict[method].get('tags', [])
        print(f"  [{method.upper():6}] {path}  {tags}")

audit_paths = [(p, m) for p, md in paths.items() for m in md if 'audit' in p.lower()]
print(f"\nAudit routes: {len(audit_paths)}")
for p, m in audit_paths:
    print(f"  [{m.upper()}] {p}")

print(f"\nTotal paths: {len(paths)}")
