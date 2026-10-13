import sys, time
sys.path.insert(0, 'backend')
from app.jobs.job_store import create_job, get_job, get_job_items
from app.jobs.runner import run_audit_sync
from app.parsers.mention_extractor import load_db_sets

load_db_sets()

rebuilt_bank = [
    {"desc": "Power Cable 1.1kV XLPE", "spec": "Conforming to IS 7098 (Part 1):1988 specification", "qty": "3000", "unit": "MTR", "code": "CBL-SUP-01"},
    {"desc": "Heavy Duty PVC Control Cable", "spec": "Conforming to IS 1554 (Part 1):1976 specification", "qty": "2000", "unit": "MTR", "code": "CBL-SUP-02"},
    {"desc": "High Strength TMT Steel Rebars", "spec": "Steel bars conforming to IS 1786:1985", "qty": "50", "unit": "MT", "code": "STL-OUT-01"},
    {"desc": "RCC Structural Concrete", "spec": "Design strictly per IS 456:1978 code of practice", "qty": "200", "unit": "CUM", "code": "CIV-OUT-02"},
    {"desc": "PVC INSULATED Copper Wire 1.1kV", "spec": "XLPE INSULATED POWER CABLE TO IS 7098 (Part 1):2025", "qty": "1500", "unit": "MTR", "code": "CBL-CON-01"},
    {"desc": "Fabricated Mild Steel Support Brackets and Clamps", "spec": "High quality galvanized steel accessories for cable tray mounting", "qty": "500", "unit": "NOS", "code": "SUP-MIS-01"},
    {"desc": "Imported Specialized Valve", "spec": "Manufactured strictly to DIN 99999 standard specification", "qty": "10", "unit": "NOS", "code": "VAL-UNK-01"},
    {"desc": "Ordinary Portland Cement 53 Grade", "spec": "Conforming to IS 269:2015 with valid BIS license and ISI mark on every bag", "qty": "5000", "unit": "BAG", "code": "CMT-OK-01"},
    {"desc": "Mild Steel Tubes Heavy Grade", "spec": "Conforming to IS 1239 (Part 1):2004 carrying standard ISI mark", "qty": "2000", "unit": "MTR", "code": "PIP-OK-02"},
    {"desc": "CBLE: PVC FRLS 1.1KV: CU-STR: 1CX1.5SQMM", "spec": "POWER CABLE :SPECIFICATION/VOLTAGE GRADE- IS : 7098 XLPE CU STRANDED", "qty": "4000", "unit": "MTR", "code": "CBL-NOYR-01"},
]

forty_items_rebuilt = []
for i in range(40):
    tmpl = rebuilt_bank[i % len(rebuilt_bank)]
    num = i + 1
    forty_items_rebuilt.append({
        "item_id": f"ITEM-{num:03d}",
        "seq_no": num,
        "description": f"{tmpl['desc']} [Item #{num}]",
        "technical_spec": tmpl["spec"],
        "quantity": tmpl["qty"],
        "unit": tmpl["unit"],
        "material_code": f"{tmpl['code']}-{num:02d}",
    })

job = create_job(['rebuilt_test'])
print(f"Starting audit sync for job {job['id']}...")
t0 = time.time()
res = run_audit_sync(job['id'], raw_items=forty_items_rebuilt)
t1 = time.time()
print(f"Finished in {t1 - t0:.3f}s. Status: {res.get('status')}")
items = get_job_items(job['id'])
print(f"Total items in DB: {len(items)}")
statuses = {}
for it in items:
    statuses[it['status']] = statuses.get(it['status'], 0) + 1
print("Statuses:", statuses)
