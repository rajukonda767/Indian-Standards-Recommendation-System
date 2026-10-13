import json, sys

with open(r"C:\Users\devag\.gemini\antigravity\brain\9eb58232-caf4-49e0-b00d-7f324f33daf3\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        idx = data.get("step_index", 0)
        content = data.get("content", "")
        if "### Step 4" in content:
            lines = content.splitlines()
            for i, l in enumerate(lines):
                if "### Step 4" in l:
                    sys.stdout.buffer.write(f"[{idx}] {l}\n".encode("utf-8"))
                    for sub in lines[i+1:min(len(lines), i+40)]:
                        sys.stdout.buffer.write(f"    {sub}\n".encode("utf-8"))
                    sys.stdout.buffer.write(b"="*60 + b"\n")
