"""
SIH-26108 — Hardening v3: virtual_scope injection
Reads sih_bis_mvp_400_hardened_v2.xlsx (never modifies it).
Writes sih_bis_mvp_400_hardened_v3.xlsx.

virtual_scope template:
  [Title]: {title}. [Classification]: Under {Dept} / {Committee}, categorized under
  {Group} > {SubGroup} > {SubSubGroup} ({Ministry}). [Covered Varieties & Grades]:
  {cleaned_varieties}. [Key Test Methods & Allied Standards]: {ref_section}.

All fields derived strictly from data already in the workbook — zero hallucination.
"""

import openpyxl, re, statistics, pathlib
from collections import defaultdict
from openpyxl.styles import PatternFill, Font, Alignment

IN_XLSX  = pathlib.Path('sih_bis_mvp_400_hardened_v2.xlsx')
OUT_XLSX = pathlib.Path('sih_bis_mvp_400_hardened_v3.xlsx')

HEADER_FILL = PatternFill('solid', fgColor='1F4E79')
HEADER_FONT = Font(color='FFFFFF', bold=True)

# ── 1. Load source workbook ─────────────────────────────────────────────────

print('Loading source workbook...')
wb_in = openpyxl.load_workbook(IN_XLSX)


# ── 2. Build lookup tables ──────────────────────────────────────────────────

# 2a. Licence Varieties  →  sn -> product_varieties string
print('Building variety lookup...')
ws_lic = wb_in['Licence Varieties']
lic_h  = [c.value for c in ws_lic[1]]
lic_sn_idx = lic_h.index('standardNumber')
lic_pv_idx = lic_h.index('product_varieties')

variety_by_sn = {}  # standardNumber -> cleaned variety string
for row in ws_lic.iter_rows(min_row=2, values_only=True):
    sn = (row[lic_sn_idx] or '').strip()
    pv = (str(row[lic_pv_idx]) if row[lic_pv_idx] else '').strip()
    if sn and pv and pv not in ('None', 'nan', ''):
        variety_by_sn[sn] = pv

print(f'  variety_by_sn: {len(variety_by_sn)} entries')


# 2b. Allied & References (Hardened) → sn -> {edge_type: [titles]}
print('Building reference lookup...')
ws_edge = wb_in['Allied & References (Hardened)']
edge_h  = [c.value for c in ws_edge[1]]
e_src   = edge_h.index('source_standardNumber')
e_title = edge_h.index('ref_title')
e_type  = edge_h.index('edge_type')

refs_by_sn = defaultdict(lambda: defaultdict(list))  # sn -> edge_type -> [title]

for row in ws_edge.iter_rows(min_row=2, values_only=True):
    src_sn = (row[e_src] or '').strip()
    title  = (row[e_title] or '').strip()
    etype  = (row[e_type]  or 'REFERENCED_UNKNOWN').strip()
    if src_sn and title:
        refs_by_sn[src_sn][etype].append(title)

print(f'  refs_by_sn: {len(refs_by_sn)} source standards have references')


# ── 3. Helper functions ─────────────────────────────────────────────────────

def clean_ws(text):
    """Collapse whitespace, strip leading/trailing, remove raw newlines."""
    if not text:
        return ''
    return re.sub(r'\s+', ' ', str(text)).strip()


def join_nonempty(*parts, sep='. '):
    """Join non-empty, non-None parts with separator."""
    return sep.join(p for p in parts if p and str(p).strip() not in ('', 'None', 'nan'))


def format_ref_section(ref_dict):
    """
    Build a concise reference section from {edge_type: [title, ...]} dict.
    Groups into Test Methods / Components & Materials / Related Standards.
    Caps at 5 titles per group to keep scope readable.
    """
    if not ref_dict:
        return ''

    # Map edge_type → display group
    GROUP_MAP = {
        'TEST_METHOD':        'Test Methods',
        'TERMINOLOGY':        'Terminology',
        'INSTALLATION_CODE':  'Codes of Practice',
        'SAFETY_STANDARD':    'Safety Standards',
        'COMPONENT_PRODUCT':  'Components & Materials',
        'REFERENCED_UNKNOWN': 'Related Standards',
    }

    groups = {}
    for etype, group_label in GROUP_MAP.items():
        titles = ref_dict.get(etype, [])
        if not titles:
            continue
        # Deduplicate preserving order
        seen = set()
        unique = []
        for t in titles:
            key = t[:50].lower()
            if key not in seen:
                seen.add(key)
                unique.append(clean_ws(t))
        # Cap at 5 per group
        capped = unique[:5]
        if len(unique) > 5:
            capped.append(f'(+{len(unique)-5} more)')
        groups[group_label] = capped

    if not groups:
        return ''

    parts = []
    for label, titles in groups.items():
        parts.append(f'{label}: {"; ".join(titles)}')
    return '. '.join(parts)


def build_virtual_scope(row_dict, variety_by_sn, refs_by_sn):
    """
    Construct the deterministic virtual_scope string for one standard.
    row_dict: {header: value} from Standards Master row.
    """
    sn      = clean_ws(row_dict.get('Standard Number', ''))
    title   = clean_ws(row_dict.get('Title', ''))
    dept    = clean_ws(row_dict.get('Dept', ''))
    comm    = clean_ws(row_dict.get('Technical Committee', ''))
    ministry= clean_ws(row_dict.get('Ministry', ''))
    group   = clean_ws(row_dict.get('Group', ''))
    subgrp  = clean_ws(row_dict.get('SubGroup', ''))
    subsubg = clean_ws(row_dict.get('SubSubGroup', ''))
    cert    = clean_ws(row_dict.get('Certification', ''))
    std_type= clean_ws(row_dict.get('Type of Standard', ''))

    # Section 1: Title
    title_part = f'[Title]: {sn} — {title}' if title else f'[Title]: {sn}'

    # Section 2: Classification
    # Build classification chain — skip blanks gracefully
    dept_comm = join_nonempty(dept, comm, sep=' / ') if dept or comm else ''
    chain_parts = [g for g in [group, subgrp, subsubg] if g]
    chain = ' > '.join(chain_parts) if chain_parts else ''
    ministry_part = f'({ministry})' if ministry else ''

    class_parts = []
    if dept_comm:
        class_parts.append(f'Under {dept_comm}')
    if chain:
        cat_str = f'categorized under {chain}'
        if ministry_part:
            cat_str += f' {ministry_part}'
        class_parts.append(cat_str)
    elif ministry_part:
        class_parts.append(f'Ministry: {ministry}')

    if cert:
        class_parts.append(f'Certification: {cert}')
    if std_type:
        class_parts.append(f'Type: {std_type}')

    class_section = (f'[Classification]: {", ".join(class_parts)}'
                     if class_parts else '')

    # Section 3: Varieties & Grades (from Licence Varieties sheet)
    pv = variety_by_sn.get(sn, '')
    variety_section = f'[Covered Varieties & Grades]: {pv}' if pv else ''

    # Section 4: References (from Allied & References (Hardened))
    ref_dict = refs_by_sn.get(sn, {})
    ref_text = format_ref_section(ref_dict)
    ref_section = f'[Key Test Methods & Allied Standards]: {ref_text}' if ref_text else ''

    # Combine all non-empty sections
    scope = join_nonempty(title_part, class_section, variety_section, ref_section, sep='. ')
    # Final whitespace normalisation
    scope = re.sub(r'\s+', ' ', scope).strip()
    return scope


# ── 4. Build v3 workbook ────────────────────────────────────────────────────

print('Building v3 workbook...')
wb_out = openpyxl.Workbook()

# Copy all sheets from v2, adding virtual_scope to Standards Master only
MASTER_SHEET = 'Standards Master (400)'

for sheet_name in wb_in.sheetnames:
    ws_src = wb_in[sheet_name]
    ws_dst = wb_out.create_sheet(sheet_name)

    src_headers = [c.value for c in ws_src[1]]

    if sheet_name == MASTER_SHEET:
        master_src_headers = list(src_headers)  # capture before any other sheet overwrites

        # Add virtual_scope as the last column
        new_headers = src_headers + ['virtual_scope']
        ws_dst.append(new_headers)
        # Style header
        for cell in ws_dst[1]:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal='center')

        # Write data rows
        scope_lengths = []
        empty_scope   = 0

        for row in ws_src.iter_rows(min_row=2, values_only=True):
            row_dict = {src_headers[i]: row[i] for i in range(len(src_headers))}
            scope = build_virtual_scope(row_dict, variety_by_sn, refs_by_sn)

            if scope:
                scope_lengths.append(len(scope))
            else:
                empty_scope += 1

            ws_dst.append(list(row) + [scope])

        print(f'  Standards Master: {ws_dst.max_row-1} rows written')
        print(f'  Empty scopes: {empty_scope}')
        if scope_lengths:
            print(f'  Scope lengths — min:{min(scope_lengths)}  '
                  f'median:{int(statistics.median(scope_lengths))}  '
                  f'max:{max(scope_lengths)}')

    else:
        # Copy sheet verbatim
        for row in ws_src.iter_rows(values_only=True):
            ws_dst.append(list(row))
        # Re-apply header style
        for cell in ws_dst[1]:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT

# Remove default empty sheet
if 'Sheet' in wb_out.sheetnames:
    del wb_out['Sheet']

print(f'Saving {OUT_XLSX}...')
wb_out.save(OUT_XLSX)
print('Saved.')


# ── 5. Verification — re-read from disk ─────────────────────────────────────

print()
print('='*70)
print('VERIFICATION (re-reading from disk)')
print('='*70)

wb_v = openpyxl.load_workbook(OUT_XLSX)
print(f'Sheets: {wb_v.sheetnames}')
print()

ws_v = wb_v[MASTER_SHEET]
v_headers = [c.value for c in ws_v[1]]

print(f'Standards Master — cols: {ws_v.max_column} ({v_headers[-3:]}...last 3)')
print(f'  virtual_scope in headers: {"virtual_scope" in v_headers}')
print(f'  All original cols preserved: {master_src_headers == v_headers[:len(master_src_headers)]}')

vs_idx = v_headers.index('virtual_scope')
sn_idx = v_headers.index('Standard Number')
dept_idx = v_headers.index('Dept')

all_scopes = []
for row in ws_v.iter_rows(min_row=2, values_only=True):
    sc = str(row[vs_idx] or '').strip()
    all_scopes.append((row[sn_idx], row[dept_idx], sc))

non_empty = sum(1 for _, _, sc in all_scopes if sc)
lengths   = [len(sc) for _, _, sc in all_scopes if sc]
print(f'  Non-empty virtual_scope: {non_empty} / {len(all_scopes)}  (target: 400/400)')

if lengths:
    print(f'  Min length:    {min(lengths)} chars')
    print(f'  Median length: {int(statistics.median(lengths))} chars')
    print(f'  Max length:    {max(lengths)} chars')

# ── Sample 1: Civil — IS 1786 (TMT bars / Mandatory steel)
print()
print('-'*60)
print('SAMPLE 1 — Civil/Structural (IS 1786:2008 — TMT Bars)')
print('-'*60)
for sn, dept, sc in all_scopes:
    if '1786' in str(sn or '') and '2008' in str(sn or ''):
        print(sc)
        break

# ── Sample 2: Civil — IS 269:2015 (Cement)
print()
print('-'*60)
print('SAMPLE 2 — Civil (IS 269:2015 — Cement)')
print('-'*60)
for sn, dept, sc in all_scopes:
    if '269' in str(sn or '') and '2015' in str(sn or ''):
        print(sc)
        break

# ── Sample 3: Electrotechnical — IS 15086 (Surge Arresters)
print()
print('-'*60)
print('SAMPLE 3 — Electrotechnical (IS 15086)')
print('-'*60)
for sn, dept, sc in all_scopes:
    if '15086' in str(sn or ''):
        print(sc)
        break

# ── Sample 4: Zero licensed varieties (fallback check)
print()
print('-'*60)
print('SAMPLE 4 — Standard with ZERO licensed varieties (fallback)')
print('-'*60)
sn_with_lic = set(variety_by_sn.keys())
shown = False
for sn, dept, sc in all_scopes:
    if str(sn or '') not in sn_with_lic and sc:
        print(f'Standard: {sn}')
        print(sc)
        shown = True
        break
if not shown:
    print('(all standards have varieties — unexpected)')

print()
print('='*70)
print('VERIFICATION COMPLETE')
print('='*70)
