# -*- coding: utf-8 -*-
"""
tests/eval/run_gem_block_sequence.py  (v2)
Implements correct section tracking: GeMARPTS labels are heading blocks;
IS mentions in the NEXT block(s) inherit the label's tier.
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\tests\eval')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
import pymupdf
from mention_extractor import extract_mentions, load_db_sets
load_db_sets()

PDF2 = r"C:\Users\devag\Downloads\_Uploads_job_45941.pdf"

# ── GeMARPTS section label definitions ───────────────────────────────────────
# English label (as it appears after stripping Devanagari) → section tier
LABEL_TIER = {
    "Searched Strings used in GeMARPTS":               "CONTEXT_ONLY",
    "Searched Result generated in GeMARPTS":           "CONTEXT_ONLY",
    "Relevant Categories selected for notification":   "CORROBORATING",
}
# Any OTHER heading class ends the GeMARPTS-controlled section.
# Pattern: "any class not in LABEL_TIER" that looks like a structural heading.
OTHER_HEADING_RE = re.compile(
    r'\b(?:General\s+Terms|GTC|Additional\s+Terms|ATC|Buyer\s+Added'
    r'|Technical\s+Spec|Schedule\s+of\s+Req|Scope\s+of\s+Work|BOQ|Annexure'
    r'|Bid\s+Details|EMD\s+Detail|TReDS|MSE|Make\s+In\s+India)\b',
    re.IGNORECASE
)

DEVANAGARI_THRESH = 0.35

def devanagari_ratio(text):
    dev = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)
    return dev / max(len(text), 1)

def strip_devanagari(text):
    return ''.join(c for c in text if not (0x0900 <= ord(c) <= 0x097F))

def classify_label(english_text: str):
    """Return tier string if this block IS a known GeMARPTS label heading, else None."""
    t = english_text.strip()
    for label, tier in LABEL_TIER.items():
        if label.lower() in t.lower():
            return tier, label
    return None, None

doc = pymupdf.open(PDF2)
print(f"PDF-2: {PDF2}  ({len(doc)} pages)")

# ── Page 1: full annotated block sequence ────────────────────────────────────
print(f"\n{'='*90}")
print("PAGE 1: Full annotated block sequence")
print(f"{'='*90}")

page1 = doc[0]
blocks1 = page1.get_text("blocks", sort=True)

current_section_tier = "AUTHORITATIVE"
current_section_label = "default"

p1_mentions_by_key = {}   # base_key -> list[tier]

for bidx, b in enumerate(blocks1):
    btext = b[4]
    dev_r = devanagari_ratio(btext)
    english = strip_devanagari(btext)
    english_clean = re.sub(r'\s+', ' ', english).strip()

    # Check if this block is a GeMARPTS label heading
    label_tier, matched_label = classify_label(english_clean)

    # Check if this block ends the current GeMARPTS section (any OTHER heading)
    is_other_heading = bool(OTHER_HEADING_RE.search(english_clean))

    if label_tier is not None:
        # This block IS a GeMARPTS section label
        current_section_tier = label_tier
        current_section_label = matched_label
        block_tier = label_tier          # the label block itself gets the tier
        tier_reason = f"LABEL → {matched_label[:40]!r}"
    elif is_other_heading and current_section_tier != "AUTHORITATIVE":
        # This heading ends the GeMARPTS section
        current_section_tier = "AUTHORITATIVE"
        current_section_label = "default"
        block_tier = "AUTHORITATIVE"
        tier_reason = "OTHER_HEADING → section ended"
    elif dev_r > DEVANAGARI_THRESH:
        # Garbled block with no IS mentions after stripping
        block_tier = "CONTEXT_ONLY"
        tier_reason = f"garbled {dev_r:.0%}"
    else:
        # Inherit from current section
        block_tier = current_section_tier
        tier_reason = f"section={current_section_label[:35]!r}"

    # Extract mentions from English text; apply block tier
    mentions = [m for m in extract_mentions(english, block_tier) if m.disposition == 'KEEP']

    # Collect for assertions
    for mn in mentions:
        key = mn.base_key.replace(' +NO_PART', '')
        p1_mentions_by_key.setdefault(key, []).append(block_tier)

    # Print
    text_preview = english_clean[:80]
    print(f"\n  Block {bidx:02d}  tier={block_tier:<15} dev={dev_r:.0%}  [{tier_reason}]")
    print(f"    Raw:  {btext[:100].replace(chr(10), '↵')!r}")
    if mentions:
        for mn in mentions:
            ctx_b = mn.context_before[-30:] if hasattr(mn, 'context_before') else ''
            print(f"    ↳ IS: {mn.base_key:<30} disp={mn.disposition}")

# ── Assertions ────────────────────────────────────────────────────────────────
print(f"\n{'='*90}")
print("ASSERTIONS: Page 1 IS mention tier checks")
print(f"{'='*90}")

print("\nAll IS mentions on Page 1 with assigned tier(s):")
for key, tiers in p1_mentions_by_key.items():
    print(f"  {key:<30} tiers={list(set(tiers))}")

print("\nAssertion results:")
EXPECTED = {
    'IS694':         'CONTEXT_ONLY',
    'IS4989':        'CONTEXT_ONLY',
    'IS1554(PART1)': 'CONTEXT_ONLY',
    'IS7098(PART1)': 'CORROBORATING',
}
all_pass = True
for key, expected_tier in EXPECTED.items():
    tiers = p1_mentions_by_key.get(key, [])
    ok = expected_tier in tiers
    status = 'PASS ✓' if ok else 'FAIL ✗'
    if not ok: all_pass = False
    print(f"  {key:<20} expected={expected_tier:<15} got={list(set(tiers))}  {status}")

print(f"\nOverall: {'ALL PASS ✓' if all_pass else 'SOME FAIL ✗ — inspect block sequence above'}")

# ── Per-page tier ranges ──────────────────────────────────────────────────────
print(f"\n{'='*90}")
print("PER-PAGE TIER RANGES (all 8 pages, GTC ends at any other heading class)")
print(f"{'='*90}")

current_section_tier = "AUTHORITATIVE"
current_section_label = "default"

for pno in range(len(doc)):
    page = doc[pno]
    blocks = page.get_text("blocks", sort=True)
    dev_r_page = devanagari_ratio(page.get_text("text"))
    page_tiers = set()
    page_mentions = 0

    for b in blocks:
        btext = b[4]
        dev_r = devanagari_ratio(btext)
        english = strip_devanagari(btext)
        english_clean = re.sub(r'\s+', ' ', english).strip()

        label_tier, matched_label = classify_label(english_clean)
        is_other_heading = bool(OTHER_HEADING_RE.search(english_clean))

        if label_tier is not None:
            current_section_tier = label_tier
            current_section_label = matched_label
            block_tier = label_tier
        elif is_other_heading and current_section_tier != "AUTHORITATIVE":
            current_section_tier = "AUTHORITATIVE"
            block_tier = "AUTHORITATIVE"
        elif dev_r > DEVANAGARI_THRESH:
            block_tier = "CONTEXT_ONLY"
        else:
            block_tier = current_section_tier

        page_tiers.add(block_tier)
        ms = [m for m in extract_mentions(english, block_tier) if m.disposition == 'KEEP']
        page_mentions += len(ms)

    print(f"  p{pno+1}: dev={dev_r_page:.0%}  "
          f"tiers={sorted(page_tiers):<55}  IS_mentions={page_mentions}")
