import urllib.request
import json

queries = [
    ("Cable", "PVC insulated copper cable 1.5 sq mm for house wiring 1100V"),
    ("Cement", "43 grade ordinary portland cement 50kg bag for RCC construction"),
    ("Steel", "TMT 500D thermo mechanically treated steel bars 12mm for reinforced concrete")
]

for label, q in queries:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/recommend",
        data=json.dumps({"query": q}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    primary = data["primary"][0]
    print("=" * 80)
    print(f"COMMODITY: {label}")
    print(f"QUERY: \"{q}\"")
    print(f"TOP STANDARD: {primary['standard_number']} — {primary['title']}")
    print(f"CONFIDENCE: {primary['confidence']}% | STATUS: {primary['is_status_label']}")
    print(f"GROQ-GENERATED WHY-TEXT:\n\"{primary['why']}\"")
