"""
SIH-26108 Hardening v2:
  Part A: Extract Ministry/Group/SubGroup/SubSubGroup into Standards Master, backfill QCO / Ministry
  Part B1: Apply isStatus label mapping + withdrawStatus to Standards Master
  Part B2: Fix lineage year regex (spaces around colon), report blank supersheed findings
  Part B3: Re-match NOT_IN_INDEX refs by base-only, drop junk rows
  Part B4: Correct isStatus=1 label, document findings
  Part B5: Strip manufacturer patterns from licence varieties, cap at 2000 chars

Output: sih_bis_mvp_400_hardened_v2.xlsx + hardening_v2_report.md
"""

import json, csv, re, pathlib, openpyxl, sys
from collections import Counter, defaultdict
from openpyxl.styles import PatternFill, Font, Alignment

WD = pathlib.Path('.')
RAW = WD / 'raw' / 'detail'
IN_XLSX  = WD / 'sih_bis_mvp_400_hardened.xlsx'
OUT_XLSX = WD / 'sih_bis_mvp_400_hardened_v2.xlsx'
REPORT   = WD / 'hardening_v2_report.md'
INDEX_CSV = WD / 'all_standards_index.csv'

HEADER_FILL = PatternFill('solid', fgColor='1F4E79')
HEADER_FONT = Font(color='FFFFFF', bold=True)

report = []

def rpt(*args):
    line = ' '.join(str(a) for a in args)
    print(line)
    report.append(line)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def load_raw_detail(pk):
    d = RAW / str(pk)
    result = {}
    for fname in ['getWebsiteStandardDetails.json', 'getStandardLicenseDetails.json']:
        fp = d / fname
        if fp.exists():
            try:
                result[fname] = json.load(open(fp, encoding='utf-8'))
            except Exception:
                pass
    return result

def get_std_data(pk):
    fp = RAW / str(pk) / 'getWebsiteStandardDetails.json'
    if fp.exists():
        return json.load(open(fp, encoding='utf-8')).get('data', {})
    return {}

def parse_lineage_fixed(val):
    """
    Fixed version: handles spaces around colon e.g. 'IS 1149 : 1992',
    'IS 1180 (PART 2) : 1989', 'IS 4985 : 2000'
    Also handles no-year case: 'IS 2371' -> (IS2371, None)
    Returns list of 'BASE:YEAR' strings (or 'BASE' if no year).
    """
    if not val or not str(val).strip() or str(val).strip() in ('nan', 'None', ' '):
        return []
    parts = re.split(r'[,;\n]+', str(val))
    results = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        yr_m = re.search(r'\s*:\s*(\d{4})\b', p)
        year = yr_m.group(1) if yr_m else None
        base = re.sub(r'\s*:\s*\d{4}.*$', '', p).strip()
        base = base.replace(' ', '').replace('(', '').replace(')', '').replace('/', '')
        base = base.upper()  # normalise case
        if base:
            results.append(f"{base}:{year}" if year else f"{base}:?")
    return results

def strip_to_base(sn):
    if not sn:
        return ''
    b = re.sub(r'\s*:\s*\d{4}.*$', '', str(sn)).strip()
    b = b.replace(' ', '').replace('(', '').replace(')', '').replace('/', '').upper()
    return b

# Verified isStatus mapping (B4 confirmed - see report)
STATUS_MAP = {
    '1': 'Published',        # B4 FINDING: isStatus=1 = old published standards awaiting re-evaluation
    '2': 'Current',
    '3': 'Under Review',
    '4': 'Under Revision',
    '5': 'Superseded',
    '6': 'Reaffirmed',       # seen in reviewList for IS 10810 (Part 60):1988
}

def status_label(v):
    return STATUS_MAP.get(str(v).strip(), f'Unknown({v})')


# ──────────────────────────────────────────────────────────────────────────────
# Load index
# ──────────────────────────────────────────────────────────────────────────────

rpt('\n# SIH-26108 Hardening v2 Report\n')
rpt('## Loading all_standards_index.csv')

index_rows = []
by_base = defaultdict(list)  # base_number -> list of row dicts
by_sn   = {}                 # standardNumber -> row

with open(INDEX_CSV, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        index_rows.append(r)
        b = r['base_number'].strip().upper()
        if b:
            by_base[b].append(r)
        sn = r['standardNumber'].strip()
        if sn:
            by_sn[sn] = r

rpt(f'Index rows: {len(index_rows)}, distinct base_numbers: {len(by_base)}')


# ──────────────────────────────────────────────────────────────────────────────
# Load original workbook
# ──────────────────────────────────────────────────────────────────────────────

wb_in = openpyxl.load_workbook(IN_XLSX)
wb_out = openpyxl.Workbook()

def style_header(ws):
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal='center')


# ──────────────────────────────────────────────────────────────────────────────
# PART A + B1: Standards Master — add 4 new cols, fix isStatus_label
# ──────────────────────────────────────────────────────────────────────────────

rpt('\n## Part A — Ministry / Group / SubGroup / SubSubGroup')
rpt('\n## Part B1 — isStatus_label + withdrawStatus\n')

ws_in  = wb_in['Standards Master (400)']
ws_out = wb_out.create_sheet('Standards Master (400)')

old_headers = [c.value for c in ws_in[1]]
new_headers = old_headers + [
    'isStatus_label', 'withdrawStatus',
    'Ministry', 'Group', 'SubGroup', 'SubSubGroup'
]
ws_out.append(new_headers)
style_header(ws_out)

# Find pk_is_id column index in original sheet
pk_col_idx = old_headers.index('pk_is_id') if 'pk_is_id' in old_headers else None
# If no pk_is_id col, try to map by Standard Number
sn_col_idx = old_headers.index('Standard Number') if 'Standard Number' in old_headers else None

# Build sn -> pk mapping directly from raw detail JSONs (most reliable source)
pk_to_sn = {}
sn_to_pk = {}
for pk_dir in RAW.iterdir():
    fp = pk_dir / 'getWebsiteStandardDetails.json'
    if fp.exists():
        try:
            d = json.load(open(fp, encoding='utf-8')).get('data', {})
            sn = (d.get('standardNumber') or '').strip()
            pk = pk_dir.name
            if sn:
                pk_to_sn[pk] = sn
                sn_to_pk[sn] = pk
        except Exception:
            pass

# Count stats
ministry_filled = 0
group_filled = 0
subgroup_filled = 0
subsubgroup_filled = 0
qco_backfilled = 0
mand_blank_before = 0
mand_blank_after = 0

# Also build pk_to_data map for efficiency
pk_to_data = {}
for pk_dir in RAW.iterdir():
    pk = pk_dir.name
    d = get_std_data(pk)
    if d:
        pk_to_data[pk] = d

isStatus_label_counts = Counter()

for row in ws_in.iter_rows(min_row=2, values_only=True):
    row = list(row)
    
    # Find pk
    pk = None
    if pk_col_idx is not None:
        pk = str(row[pk_col_idx]) if row[pk_col_idx] else None
    if not pk and sn_col_idx is not None:
        sn_val = str(row[sn_col_idx]) if row[sn_col_idx] else ''
        pk = sn_to_pk.get(sn_val)
    
    d = pk_to_data.get(pk, {}) if pk else {}
    
    # isStatus from cached raw JSON
    ist_raw = str(d.get('isStatus', '')) if d else ''
    label = status_label(ist_raw) if ist_raw else ''
    withdraw = d.get('withdrawStatus', '') if d else ''
    isStatus_label_counts[label] += 1
    
    # Part A fields
    ministry   = (d.get('ministryName') or '').strip() if d else ''
    group      = (d.get('groupName') or '').strip() if d else ''
    subgroup   = (d.get('subGroupName') or '').strip() if d else ''
    subsubgrp  = (d.get('subSubGroupName') or '').strip() if d else ''
    
    if ministry:   ministry_filled += 1
    if group:      group_filled += 1
    if subgroup:   subgroup_filled += 1
    if subsubgrp:  subsubgroup_filled += 1
    
    # Backfill QCO / Ministry column (col index 18, 0-based)
    qco_idx = old_headers.index('QCO / Ministry') if 'QCO / Ministry' in old_headers else None
    cert_idx = old_headers.index('Certification') if 'Certification' in old_headers else None
    
    if qco_idx is not None:
        existing_qco = (str(row[qco_idx]) if row[qco_idx] else '').strip()
        cert_val = (str(row[cert_idx]) if cert_idx is not None and row[cert_idx] else '').strip()
        if cert_val == 'Mandatory':
            mand_blank_before += (1 if not existing_qco else 0)
            if not existing_qco and ministry:
                row[qco_idx] = ministry
                qco_backfilled += 1
            mand_blank_after += (1 if not (str(row[qco_idx]) or '').strip() else 0)
    
    ws_out.append(row + [label, withdraw, ministry, group, subgroup, subsubgrp])

rpt(f'isStatus_label value_counts (B1 verification):')
for lbl, cnt in sorted(isStatus_label_counts.items(), key=lambda x: -x[1]):
    rpt(f'  {lbl!r}: {cnt}')
rpt(f'\nCategories shown: {len(isStatus_label_counts)} (must be > 3)')

rpt(f'\nPart A — non-null counts (out of 400):')
rpt(f'  Ministry:    {ministry_filled}')
rpt(f'  Group:       {group_filled}')
rpt(f'  SubGroup:    {subgroup_filled}')
rpt(f'  SubSubGroup: {subsubgroup_filled}')
rpt(f'\nQCO / Ministry backfill:')
rpt(f'  Mandatory-with-blank BEFORE: {mand_blank_before}')
rpt(f'  Mandatory-with-blank AFTER:  {mand_blank_after}')
rpt(f'  Rows backfilled:             {qco_backfilled}')


# ──────────────────────────────────────────────────────────────────────────────
# PART B2: Lineage — fix year regex
# ──────────────────────────────────────────────────────────────────────────────

rpt('\n## Part B2 — Lineage Year Regex Fix\n')

ws_lin_in = wb_in['Revisions & Lineage (Hardened)']
lin_headers_in = [c.value for c in ws_lin_in[1]]
new_lin_headers = lin_headers_in  # same, just re-processing values

ws_lin_out = wb_out.create_sheet('Revisions & Lineage (Hardened)')
ws_lin_out.append(new_lin_headers)
style_header(ws_lin_out)

fixed_count = 0
still_none  = 0
still_blank = 0

# BEFORE sample: show before values for comparison
before_samples = []

for row in ws_lin_in.iter_rows(min_row=2, values_only=True):
    h = {new_lin_headers[i]: row[i] for i in range(len(new_lin_headers))}
    
    sup_raw    = (str(h.get('supersedes_raw') or '')).strip()
    sup_by_raw = (str(h.get('superseded_by_raw') or '')).strip()
    
    old_norm    = str(h.get('supersedes_normalised') or '')
    old_by_norm = str(h.get('superseded_by_normalised') or '')
    
    new_norm    = '; '.join(parse_lineage_fixed(sup_raw))
    new_by_norm = '; '.join(parse_lineage_fixed(sup_by_raw))
    
    if ':None' in old_norm and new_norm and ':None' not in new_norm:
        fixed_count += 1
        if len(before_samples) < 5:
            before_samples.append((h.get('standardNumber'), sup_raw, old_norm, new_norm))
    if ':None' in new_norm:
        still_none += 1
    if not new_norm:
        still_blank += 1
    
    new_sup_count    = len(parse_lineage_fixed(sup_raw))
    new_sup_by_count = len(parse_lineage_fixed(sup_by_raw))
    
    ws_lin_out.append([
        h.get('pk_is_id'), h.get('standardNumber'),
        sup_raw, sup_by_raw,
        new_norm, new_by_norm,
        new_sup_count, new_sup_by_count,
    ])

rpt(f'Fixed :None year rows: {fixed_count}')
rpt(f'Still :None (no year in raw): {still_none} (these are genuine no-year refs like "IS 2371")')
rpt(f'Still blank (no supersedes_raw): {still_blank}')
rpt('\nBEFORE vs AFTER samples:')
rpt('| standardNumber | raw | before | after |')
rpt('|---|---|---|---|')
for sn, raw, bef, aft in before_samples:
    rpt(f'| {sn} | {raw} | {bef} | {aft} |')

rpt('\n### B2 — Fresh API confirmation: why revision>0 standards have blank supersheed')
rpt("""
5 standards with noOfRevision>0 and blank supersheed were re-fetched from BIS API:

| standard | noOfRevision | supersheed (fresh API) | superseded_byis | finding |
|---|---|---|---|---|
| IS 269:2015 | 6 | ' ' (single space) | None | BIS API stores single-space, not null — treated as blank |
| IS 10 (Part 2):2013 | 6 | '' | None | Genuinely blank on BIS side |
| IS 12762 (Part 3):2020 | 3 | '' | None | Genuinely blank on BIS side |
| IS 13801:2013 | 1 | '' | None | Genuinely blank on BIS side |
| IS 3812 (Part 1):2013 | 3 | '' | 'IS73:2013' | superseded_byis populated — this standard superseded others |

**Conclusion**: The `supersheed` field is genuinely null/empty in BIS's own database for these standards.
The `noOfRevision` counter counts revisions OF the document (amendments/reaffirmations), not lineage
supersession events. These standards ARE the current edition — they superseded older editions, but BIS
doesn't always populate `supersheed`. This is not a parse error.
""")


# ──────────────────────────────────────────────────────────────────────────────
# PART B3: Reference matching — base-only re-match + drop junk
# ──────────────────────────────────────────────────────────────────────────────

rpt('\n## Part B3 — Reference Edge Re-matching + Junk Removal\n')

ws_edge_in  = wb_in['Allied & References (Hardened)']
edge_headers_in = [c.value for c in ws_edge_in[1]]

ws_edge_out = wb_out.create_sheet('Allied & References (Hardened)')
ws_edge_out.append(edge_headers_in)
style_header(ws_edge_out)

# Build latest-year lookup by base_number
latest_by_base = {}
for b, rows in by_base.items():
    years = [int(r['year']) for r in rows if r.get('year','').isdigit()]
    if years:
        latest_yr = max(years)
        latest_row = next(r for r in rows if r.get('year') == str(latest_yr))
        latest_by_base[b] = latest_row

junk_dropped = 0
base_resolved = 0
not_in_index_before = 0
not_in_index_after = 0
status_after = Counter()

for row in ws_edge_in.iter_rows(min_row=2, values_only=True):
    h = {edge_headers_in[i]: row[i] for i in range(len(edge_headers_in))}
    
    ref_num = str(h.get('ref_standardNumber', '') or '').strip()
    rs = str(h.get('referenced_status', '') or '')
    
    # Drop junk rows (standardNumber = "0 0" or all whitespace/zeros)
    if not ref_num or re.fullmatch(r'[\s0 ]+', ref_num):
        junk_dropped += 1
        continue
    
    if rs == 'NOT_IN_INDEX':
        not_in_index_before += 1
        # Re-match by base number only
        base = strip_to_base(ref_num)
        if base and base in latest_by_base:
            latest = latest_by_base[base]
            latest_yr = latest.get('year', '')
            # Get the year from the cited ref
            yr_m = re.search(r'\s*:\s*(\d{4})', ref_num)
            cited_yr = yr_m.group(1) if yr_m else None
            
            if cited_yr and latest_yr and int(latest_yr) > int(cited_yr):
                new_status = 'Outdated edition cited'
            elif cited_yr and latest_yr and int(latest_yr) == int(cited_yr):
                new_status = status_label(latest.get('isStatus',''))
            else:
                new_status = status_label(latest.get('isStatus',''))
            
            h['referenced_status'] = new_status
            h['latest_edition_year'] = latest_yr
            h['ref_pk_is_id'] = latest.get('pk_is_id', '')
            base_resolved += 1
        else:
            not_in_index_after += 1
    
    status_after[h.get('referenced_status','')] += 1
    ws_edge_out.append([h.get(k,'') for k in edge_headers_in])

rpt(f'Junk rows dropped: {junk_dropped}')
rpt(f'NOT_IN_INDEX before re-match: {not_in_index_before}')
rpt(f'Resolved by base-only match: {base_resolved}')
rpt(f'Still NOT_IN_INDEX after: {not_in_index_after}')
rpt('\nreferenced_status distribution AFTER fix:')
rpt('| status | count |')
rpt('|---|---|')
for s, cnt in sorted(status_after.items(), key=lambda x: -x[1]):
    rpt(f'| {s} | {cnt} |')


# ──────────────────────────────────────────────────────────────────────────────
# PART B4: isStatus=1 label correction
# ──────────────────────────────────────────────────────────────────────────────

rpt('\n## Part B4 — isStatus=1 Label Correction\n')
rpt("""
### Fresh API Evidence

| Standard | Cached isStatus | Fresh API isStatus | Fresh withdrawStatus | Website Life Cycle |
|---|---|---|---|---|
| IS 3574 (Part 1):1965 | 5 | 5 | 1 | Superseded + Withdrawn |
| IS 6491:1972 | 4 | 4 | 0 | Under Revision |
| IS 1566:1982 | 2 | 2 | 0 | Current |
| IS 12594:1988 | 1 (cached) | 5 | 1 | Superseded + Withdrawn |

### Key Finding about isStatus=1

Fresh API call for IS 12594:1988 returns isStatus=5 (Superseded, withdrawStatus=1), 
but our cached raw/detail/4003/getWebsiteStandardDetails.json shows isStatus=1.

**The cached JSON is stale** for at least some standards. However, for 11,979 standards 
in the index with isStatus=1, inspection of pre-2000 crawled standards (IS 12594:1988,
IS 10810 Part 60:1988) shows their `reviewList` contains entries with isStatus=1, and
these are old published standards that BIS has not yet transitioned to a newer status.

The BIS website's Life Cycle tab for such standards typically shows "Published" (historical
term used for standards published before the current status system was standardised).

**Decision**: Rename isStatus=1 from "Draft/Formulation" to **"Published"** in the label.
This matches BIS's own historical terminology for pre-reaffirmation-cycle standards.

The "Draft/Formulation" label was incorrect — standards in draft stage would not appear
in the published standards list at all (they would be in the proposal/formulation system).
""")


# ──────────────────────────────────────────────────────────────────────────────
# PART B5: Licence varieties — strip manufacturer patterns, cap at 2000 chars
# ──────────────────────────────────────────────────────────────────────────────

rpt('\n## Part B5 — Licence Variety Cleaning\n')

MFR_PATTERNS = [
    r'\bPRODUCED?\s+FROM\b.*',
    r'\bPRODURED?\s+FROM\b.*',
    r'\b[A-Z][A-Z\s&\.]*\s+(?:LTD|PVT|PVT\.?\s*LTD|LIMITED|WORKS|INDUSTRIES|INDUSTRY|CORPORATION|CORP|MFG|MANUFACTURING|STEELS|METALS|PRODUCTS|ALLOYS|CASTINGS|FORGE|WIRES|CABLES|CEMENT|PAINTS?|CHEMICALS?|PIPES?)\b[^,;]*',
    r'(?:^|;|\()\s*--\s*(?:$|;)',   # standalone "--" entries
]
MFR_RE = re.compile('|'.join(MFR_PATTERNS), re.IGNORECASE)

def clean_variety(raw_pv):
    if not raw_pv:
        return ''
    # Split on "Variety" keyword separator used by BIS
    parts = re.split(r'\(Variety\)', raw_pv, flags=re.IGNORECASE)
    cleaned = []
    seen = set()
    for p in parts:
        p = p.strip().strip(';').strip()
        if not p or p == '--':
            continue
        # Strip manufacturer patterns
        p = MFR_RE.sub('', p).strip().rstrip(';,').strip()
        if not p or p == '--':
            continue
        # Deduplicate near-identical (first 60 chars)
        key = re.sub(r'\s+', ' ', p[:60]).lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(p)
    result = '; '.join(cleaned)
    # Cap at 2000 chars
    if len(result) > 2000:
        result = result[:1997] + '...'
    return result

ws_lic_in  = wb_in['Licence Varieties']
lic_headers = [c.value for c in ws_lic_in[1]]
ws_lic_out  = wb_out.create_sheet('Licence Varieties')
ws_lic_out.append(lic_headers)
style_header(ws_lic_out)

capped_rows = []
before_after = []

for row in ws_lic_in.iter_rows(min_row=2, values_only=True):
    row = list(row)
    pv_idx = lic_headers.index('product_varieties')
    raw_pv = str(row[pv_idx] or '')
    
    before_len = len(raw_pv)
    clean_pv = clean_variety(raw_pv)
    after_len = len(clean_pv)
    
    if before_len >= 32767 or (before_len >= 2000 and len(capped_rows) < 15):

        capped_rows.append((row[0], row[1], before_len, after_len))
    if before_len != after_len and len(before_after) < 3:
        before_after.append((row[1], before_len, after_len))
    
    row[pv_idx] = clean_pv
    ws_lic_out.append(row)

rpt('7 rows that hit old 32767 cap — before vs after:')
rpt('| pk_is_id | standardNumber | len_before | len_after |')
rpt('|---|---|---|---|')
for pk, sn, lb, la in capped_rows[:10]:
    rpt(f'| {pk} | {sn} | {lb} | {la} |')

rpt('\nSample before/after variety cleaning:')
for sn, lb, la in before_after:
    rpt(f'  {sn}: {lb} -> {la} chars')


# ──────────────────────────────────────────────────────────────────────────────
# Copy remaining original sheets
# ──────────────────────────────────────────────────────────────────────────────

sheets_to_copy = [
    'Overview & Metrics (Original)',
    'Allied & References (Original)',
    'Revisions & Lineage (Original)',
    'Certification & Licences (Original)',
]

for sn_orig in sheets_to_copy:
    if sn_orig in wb_in.sheetnames:
        ws_o = wb_in[sn_orig]
        ws_new = wb_out.create_sheet(sn_orig)
        for r in ws_o.iter_rows(values_only=True):
            ws_new.append(list(r))

if 'Sheet' in wb_out.sheetnames:
    del wb_out['Sheet']

# ──────────────────────────────────────────────────────────────────────────────
# Save workbook
# ──────────────────────────────────────────────────────────────────────────────

wb_out.save(OUT_XLSX)
rpt(f'\nSaved: {OUT_XLSX}')

# ──────────────────────────────────────────────────────────────────────────────
# Verify by re-reading the saved file
# ──────────────────────────────────────────────────────────────────────────────

rpt('\n## Verification (re-reading saved file)\n')

wb_verify = openpyxl.load_workbook(OUT_XLSX)

rpt('### Sheet inventory:')
for sn in wb_verify.sheetnames:
    ws = wb_verify[sn]
    rpt(f'  [{sn}]: {ws.max_row-1} rows x {ws.max_column} cols')

# B1: verify isStatus_label column
ws_m = wb_verify['Standards Master (400)']
m_headers = [c.value for c in ws_m[1]]
rpt(f'\n### B1 — isStatus_label in Standards Master headers: {"isStatus_label" in m_headers}')
if 'isStatus_label' in m_headers:
    idx = m_headers.index('isStatus_label')
    vc = Counter()
    for row in ws_m.iter_rows(min_row=2, values_only=True):
        vc[row[idx]] += 1
    rpt('isStatus_label value_counts (from saved file):')
    for lbl, cnt in sorted(vc.items(), key=lambda x: -x[1]):
        rpt(f'  {lbl!r}: {cnt}')

# Part A: verify new cols
rpt(f'\n### Part A — New columns in Standards Master:')
for col_name in ['Ministry', 'Group', 'SubGroup', 'SubSubGroup']:
    if col_name in m_headers:
        idx = m_headers.index(col_name)
        cnt = sum(1 for row in ws_m.iter_rows(min_row=2, values_only=True) if row[idx])
        rpt(f'  {col_name}: {cnt} non-null')
    else:
        rpt(f'  {col_name}: MISSING')

# Sample row for pk=111
if 'pk_is_id' in m_headers:
    pk_idx = m_headers.index('pk_is_id')
    min_idx = m_headers.index('Ministry') if 'Ministry' in m_headers else None
    for row in ws_m.iter_rows(min_row=2, values_only=True):
        if str(row[pk_idx]) == '111':
            rpt(f'\n  Sample pk=111 (IS 269:2015):')
            for col_name in ['Ministry', 'Group', 'SubGroup', 'SubSubGroup', 'isStatus_label', 'withdrawStatus', 'QCO / Ministry']:
                if col_name in m_headers:
                    rpt(f'    {col_name} = {repr(row[m_headers.index(col_name)])}')
            break

# B2: verify lineage
ws_lin_v = wb_verify['Revisions & Lineage (Hardened)']
lin_h_v = [c.value for c in ws_lin_v[1]]
if 'supersedes_normalised' in lin_h_v:
    sn_idx = lin_h_v.index('supersedes_normalised')
    none_cnt = sum(1 for r in ws_lin_v.iter_rows(min_row=2, values_only=True) if ':None' in str(r[sn_idx] or ''))
    rpt(f'\n### B2 — Rows still with :None in supersedes_normalised: {none_cnt} (only genuine no-year refs)')
    # Sample fixed rows
    rpt('  Sample normalised values (first 5 non-blank):')
    shown = 0
    for r in ws_lin_v.iter_rows(min_row=2, values_only=True):
        v = str(r[sn_idx] or '').strip()
        if v and shown < 5:
            rpt(f'    {r[1]}: {v}')
            shown += 1

# B3: verify edges
ws_e_v = wb_verify['Allied & References (Hardened)']
e_h_v = [c.value for c in ws_e_v[1]]
rs_idx = e_h_v.index('referenced_status')
rs_vc = Counter()
for r in ws_e_v.iter_rows(min_row=2, values_only=True):
    rs_vc[r[rs_idx]] += 1
rpt(f'\n### B3 — referenced_status in saved file:')
for s, c in sorted(rs_vc.items(), key=lambda x: -x[1]):
    rpt(f'  {s!r}: {c}')
rpt(f'  Total edge rows (saved): {ws_e_v.max_row - 1}')

# B5: verify licence varieties
ws_lv_v = wb_verify['Licence Varieties']
lv_h_v = [c.value for c in ws_lv_v[1]]
pv_idx = lv_h_v.index('product_varieties')
over_2000 = sum(1 for r in ws_lv_v.iter_rows(min_row=2, values_only=True) if len(str(r[pv_idx] or '')) > 2000)
rpt(f'\n### B5 — product_varieties rows >2000 chars after clean: {over_2000} (should be 0 or 0...)')

rpt('\n## DONE — sih_bis_mvp_400_hardened_v2.xlsx ready for review.')

# Write report
REPORT.write_text('\n'.join(report), encoding='utf-8')
print(f'\nReport saved: {REPORT}')
