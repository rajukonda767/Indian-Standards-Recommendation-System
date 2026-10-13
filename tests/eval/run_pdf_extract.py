# -*- coding: utf-8 -*-
"""
Run the mention extractor over both GeM PDFs.
Print every mention (KEEP/DROP) with ~40 chars of context.
Also print spec items 10, 20, 30 from each PDF in full.
"""
import sys, os, re, pymupdf
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\tests\eval')
from mention_extractor import extract_mentions, load_db_sets, Mention
load_db_sets()

PDFS = [
    (r"C:\Users\devag\Downloads\Techical Specifications 1.pdf",  "PDF-1 Technical Specs"),
    (r"C:\Users\devag\Downloads\_Uploads_job_45941.pdf",         "PDF-2 GeM Bid Job 45941"),
]

# Garble threshold (block-level)
GARBLE_THRESH = 0.35

def devanagari_ratio(text):
    dev = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)
    return dev / max(len(text), 1)

# Heading pattern for GTC section detection
GTC_START_RE = re.compile(
    r'\b(?:General\s+Terms|GTC|Additional\s+Terms|ATC|Special\s+Terms|Buyer\s+Added\s+ATC)\b',
    re.IGNORECASE
)
TECH_HEADING_RE = re.compile(
    r'\b(?:Technical\s+Specifications?|Schedule\s+of\s+Requirements?|Bill\s+of\s+Quantities|Scope\s+of\s+Work|BOQ)\b',
    re.IGNORECASE
)

# Buyer-added ATC heading: keep AUTHORITATIVE (do NOT default to CONTEXT_ONLY)
BUYER_ATC_RE = re.compile(r'\bBuyer\s+Added\s+ATC\b', re.IGNORECASE)
# Generic GTC (not buyer-added): set CONTEXT_ONLY
GTC_BODY_RE  = re.compile(r'\b(?:General\s+Terms\s+and\s+Conditions|GTC)\b', re.IGNORECASE)

def assign_tier(block_text, in_gtc, buyer_atc_active):
    dev_r = devanagari_ratio(block_text)
    if dev_r > GARBLE_THRESH:
        return 'CONTEXT_ONLY', f'garbled {dev_r:.0%}'
    if buyer_atc_active:
        return 'AUTHORITATIVE', 'buyer_ATC'   # Point 7: buyer ATC stays AUTHORITATIVE
    if in_gtc:
        return 'CONTEXT_ONLY', 'GTC'
    return 'AUTHORITATIVE', ''

for pdf_path, pdf_label in PDFS:
    print(f"\n{'='*90}")
    print(f"PDF: {pdf_label}  ({pdf_path})")
    print(f"{'='*90}")
    doc = pymupdf.open(pdf_path)

    all_items = []   # (item_no, text) for numbered lines
    item_counter = 0

    in_gtc       = False
    buyer_atc    = False
    all_mentions = []

    for pno, page in enumerate(doc):
        blocks = page.get_text("blocks", sort=True)
        for b in blocks:
            btext = b[4]
            dev_r = devanagari_ratio(btext)

            # Heading detection
            if len(btext.strip()) <= 120:
                if TECH_HEADING_RE.search(btext):
                    in_gtc = False
                    buyer_atc = False
                elif BUYER_ATC_RE.search(btext):
                    buyer_atc = True
                    in_gtc = False
                elif GTC_BODY_RE.search(btext):
                    buyer_atc = False
                    in_gtc = True

            tier, reason = assign_tier(btext, in_gtc, buyer_atc)

            # If block has >35% Devanagari but contains IS mentions:
            # strip Devanagari characters, keep rest
            effective_text = btext
            if dev_r > GARBLE_THRESH:
                stripped = ''.join(c for c in btext if not (0x0900 <= ord(c) <= 0x097F))
                if re.search(r'\bIS\s*\d', stripped):
                    effective_text = stripped
                    tier = 'AUTHORITATIVE'
                    reason = f'Devanagari stripped ({dev_r:.0%}), IS mention kept'
                else:
                    effective_text = stripped

            # Collect numbered items (lines with digit prefix)
            for line in btext.split('\n'):
                line = line.strip()
                if re.match(r'^\d+[\.\)]\s', line) or (line and re.match(r'^\d+\s+[A-Z]', line)):
                    item_counter += 1
                    all_items.append((item_counter, line, f"p{pno+1}"))

            # Extract mentions
            mentions = extract_mentions(effective_text, tier)
            for mn in mentions:
                mn.context_before = btext[max(0, mn.start-40): mn.start]
                mn.context_after  = btext[mn.end: mn.end+40]
                all_mentions.append((f"p{pno+1}", tier, reason, dev_r, mn))

    # Print all mentions
    print(f"\n--- All mentions ({len(all_mentions)} total) ---")
    print(f"  {'Page':<5} {'Tier':<15} {'Disp':<6} {'Copula':<7} {'base_key':<35} Context")
    print(f"  {'-'*120}")
    for pg, tier, reason, dr, mn in all_mentions:
        ctx = f"...{mn.context_before[-35:]!r}|{mn.raw_text!r}|{mn.context_after[:35]!r}..."
        cop = 'COPULA' if mn.copula_flag else ''
        reason_tag = f" [{reason}]" if reason else ''
        print(f"  {pg:<5} {tier+reason_tag:<20} {mn.disposition:<6} {cop:<7} {mn.base_key:<35} {ctx}")

    # Print items 10, 20, 30
    print(f"\n--- Spec items #10, #20, #30 (if present) ---")
    for target in [10, 20, 30]:
        matching = [(i, t, pg) for (i, t, pg) in all_items if i == target]
        if matching:
            for (i, t, pg) in matching:
                print(f"  Item {i} ({pg}): {t}")
        else:
            print(f"  Item {target}: not found (total items found: {item_counter})")
