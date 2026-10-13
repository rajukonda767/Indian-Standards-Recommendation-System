"""
load_to_supabase.py
===================
Loads hardened BIS standards dataset from 'sih_bis_mvp_400_hardened_v3.xlsx'
into Supabase Postgres tables:
  1. standards
  2. standard_references
  3. standard_lineage
  4. licence_varieties

Reads DATABASE_URL from .env (backend/.env or .env).
Idempotent: Uses TRUNCATE CASCADE with RESTART IDENTITY before loading.
Uses fast streaming Excel reader and batch execute_values.
"""

import os
import re
import datetime
import openpyxl
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# 1. Environment and Connection Setup
if os.path.exists('backend/.env'):
    load_dotenv('backend/.env')
else:
    load_dotenv('.env')

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment or .env file!")

# Ensure sslmode=require
if 'sslmode' not in DATABASE_URL:
    sep = '&' if '?' in DATABASE_URL else '?'
    DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"

# Mask connection string for safe logging
parts = DATABASE_URL.split('@')
safe_conn_str = f"{DATABASE_URL[:12]}...@{parts[1]}" if len(parts) > 1 else "..."
print(f"Connecting to database: {safe_conn_str}", flush=True)

import sys

if len(sys.argv) > 1:
    EXCEL_FILE = sys.argv[1]
elif os.path.exists('sih_bis_full_5585.xlsx'):
    EXCEL_FILE = 'sih_bis_full_5585.xlsx'
elif os.path.exists('../sih_bis_full_5585.xlsx'):
    EXCEL_FILE = '../sih_bis_full_5585.xlsx'
elif os.path.exists('sih_bis_mvp_400_hardened_v3.xlsx'):
    EXCEL_FILE = 'sih_bis_mvp_400_hardened_v3.xlsx'
else:
    EXCEL_FILE = '../sih_bis_mvp_400_hardened_v3.xlsx'

if not os.path.exists(EXCEL_FILE):
    raise FileNotFoundError(f"Source file {EXCEL_FILE} not found!")

# 2. Parsing Helper Functions
def parse_date(v):
    if not v:
        return None
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.strftime('%Y-%m-%d')
    s = str(v).strip()
    m = re.match(r'^\d{4}-\d{2}-\d{2}', s)
    if m:
        return m.group(0)
    return None

def parse_int(v):
    if v is None:
        return None
    s = str(v).strip()
    if s.isdigit():
        return int(s)
    m = re.search(r'\b\d+\b', s)
    if m:
        return int(m.group(0))
    return None

def parse_year(v):
    if v is None:
        return None
    s = str(v).strip()
    m = re.search(r'\b(19\d\d|20\d\d)\b', s)
    if m:
        return int(m.group(1))
    return None

def parse_bool(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ('1', 'true', 't', 'yes', 'y'):
        return True
    return False

def normalize_base_number(sn):
    """
    Normalize base_number as: strip whitespace, remove ' ', uppercase, strip trailing ':YYYY'.
    """
    if not sn:
        return ''
    s = str(sn).strip().replace(' ', '').upper()
    return re.sub(r':\d{4}$', '', s)


def main():
    print(f"\nOpening workbook: {EXCEL_FILE} (fast streaming mode)...", flush=True)
    wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True, read_only=True)
    
    # -------------------------------------------------------------
    # Step 1: Parse Sheets into Memory Fast
    # -------------------------------------------------------------
    print("Reading sheets into memory...", flush=True)
    
    # Sheet 1: Standards Master (auto-detect Standards Master (5585) or (400))
    master_sheet_name = next((s for s in wb.sheetnames if 'Standards Master' in s), wb.sheetnames[0])
    print(f"Using Master Sheet: '{master_sheet_name}'", flush=True)
    ws_master = wb[master_sheet_name]
    master_rows_raw = list(ws_master.iter_rows(values_only=True))
    m_headers = [str(c or '').strip() for c in master_rows_raw[0]]
    
    standards_rows = []
    for row in master_rows_raw[1:]:
        row_dict = {m_headers[i]: row[i] for i in range(len(m_headers))}
        sn = str(row_dict.get('Standard Number') or '').strip()
        if not sn:
            continue
        
        base_no = normalize_base_number(sn)
        yr = parse_year(row_dict.get('Year'))
        pub_on = parse_date(row_dict.get('Published On'))
        reaff = parse_year(row_dict.get('Reaffirmation'))
        revs = parse_int(row_dict.get('Revisions'))
        w_status = parse_bool(row_dict.get('withdrawStatus'))
        act_lic = parse_int(row_dict.get('Active Licences')) or 0
        crs_c = parse_int(row_dict.get('CRS Count')) or 0
        ref_c = parse_int(row_dict.get('References Count')) or 0
        
        standards_rows.append((
            sn,
            base_no,
            yr,
            str(row_dict.get('Dept') or '').strip() or None,
            str(row_dict.get('Title') or '').strip(),
            str(row_dict.get('Status') or '').strip() or None,
            str(row_dict.get('isStatus_label') or '').strip() or None,
            w_status,
            pub_on,
            reaff,
            revs,
            str(row_dict.get('Technical Committee') or '').strip() or None,
            str(row_dict.get('ICS Code') or '').strip() or None,
            str(row_dict.get('Type of Standard') or '').strip() or None,
            str(row_dict.get('Equivalent Standard') or '').strip() or None,
            str(row_dict.get('Certification') or '').strip() or None,
            str(row_dict.get('QCO / Ministry') or '').strip() or None,
            str(row_dict.get('Ministry') or '').strip() or None,
            str(row_dict.get('Group') or '').strip() or None,
            str(row_dict.get('SubGroup') or '').strip() or None,
            str(row_dict.get('SubSubGroup') or '').strip() or None,
            act_lic,
            crs_c,
            ref_c,
            str(row_dict.get('Supersedes (Older)') or '').strip() or None,
            str(row_dict.get('Superseded By (Newer)') or '').strip() or None,
            str(row_dict.get('Source URL') or '').strip() or None,
            str(row_dict.get('virtual_scope') or '').strip() or None,
            True  # verified
        ))
    print(f"Parsed {len(standards_rows)} standards master rows.", flush=True)

    # Sheet 2: Allied & References (Hardened)
    ws_refs = wb['Allied & References (Hardened)']
    refs_rows_raw = list(ws_refs.iter_rows(values_only=True))
    ref_headers = [str(c or '').strip() for c in refs_rows_raw[0]]
    raw_ref_items = []
    for row in refs_rows_raw[1:]:
        row_dict = {ref_headers[i]: row[i] for i in range(len(ref_headers))}
        src_sn = str(row_dict.get('source_standardNumber') or '').strip()
        ref_sn = str(row_dict.get('ref_standardNumber') or '').strip()
        if not src_sn or not ref_sn:
            continue
        raw_ref_items.append((
            src_sn,
            ref_sn,
            str(row_dict.get('ref_title') or '').strip() or None,
            str(row_dict.get('ref_pk_is_id') or '').strip() or None,
            str(row_dict.get('edge_type') or '').strip() or None,
            str(row_dict.get('referenced_status') or '').strip() or None,
            parse_year(row_dict.get('latest_edition_year'))
        ))
    print(f"Parsed {len(raw_ref_items)} reference rows.", flush=True)

    # Sheet 3: Revisions & Lineage (Hardened)
    ws_lin = wb['Revisions & Lineage (Hardened)']
    lin_rows_raw = list(ws_lin.iter_rows(values_only=True))
    lin_headers = [str(c or '').strip() for c in lin_rows_raw[0]]
    raw_lineage_items = []
    for row in lin_rows_raw[1:]:
        row_dict = {lin_headers[i]: row[i] for i in range(len(lin_headers))}
        sn = str(row_dict.get('standardNumber') or '').strip()
        if not sn:
            continue
        s_raw = str(row_dict.get('supersedes_raw') or '').strip()
        s_norm = str(row_dict.get('supersedes_normalised') or '').strip()
        sby_raw = str(row_dict.get('superseded_by_raw') or '').strip()
        sby_norm = str(row_dict.get('superseded_by_normalised') or '').strip()

        # Supersedes
        if s_norm and s_norm not in ('None', 'nan'):
            raw_parts = [p.strip() for p in s_raw.split(',') if p.strip()] if s_raw else []
            norm_parts = [p.strip() for p in s_norm.split(';') if p.strip()]
            for i, np in enumerate(norm_parts):
                raw_p = raw_parts[i] if i < len(raw_parts) else np
                if ':' in np:
                    b_part, y_part = np.rsplit(':', 1)
                    b = b_part.replace(':', '')
                    y = int(y_part) if y_part.isdigit() else None
                else:
                    b = np
                    y = None
                raw_lineage_items.append((sn, 'SUPERSEDES', raw_p, b, y))

        # Superseded By
        if sby_norm and sby_norm not in ('None', 'nan'):
            raw_parts = [p.strip() for p in sby_raw.split(',') if p.strip()] if sby_raw else []
            norm_parts = [p.strip() for p in sby_norm.split(';') if p.strip()]
            for i, np in enumerate(norm_parts):
                raw_p = raw_parts[i] if i < len(raw_parts) else np
                if ':' in np:
                    b_part, y_part = np.rsplit(':', 1)
                    b = b_part.replace(':', '')
                    y = int(y_part) if y_part.isdigit() else None
                else:
                    b = np
                    y = None
                raw_lineage_items.append((sn, 'SUPERSEDED_BY', raw_p, b, y))
    print(f"Parsed {len(raw_lineage_items)} lineage edges.", flush=True)

    # Sheet 4: Licence Varieties
    ws_lic = wb['Licence Varieties']
    lic_rows_raw = list(ws_lic.iter_rows(values_only=True))
    lic_headers = [str(c or '').strip() for c in lic_rows_raw[0]]
    raw_lic_items = []
    for row in lic_rows_raw[1:]:
        row_dict = {lic_headers[i]: row[i] for i in range(len(lic_headers))}
        sn = str(row_dict.get('standardNumber') or '').strip()
        if not sn:
            continue
        tot = parse_int(row_dict.get('total_isi_licences')) or 0
        pv = str(row_dict.get('product_varieties') or '').strip() or None
        raw_lic_items.append((sn, tot, pv))
    print(f"Parsed {len(raw_lic_items)} licence variety rows.", flush=True)

    wb.close()

    # -------------------------------------------------------------
    # Step 2: Connect to Database & Execute Batched Inserts
    # -------------------------------------------------------------
    print("\nConnecting to database with keepalive settings...", flush=True)
    conn = psycopg2.connect(
        DATABASE_URL,
        connect_timeout=15,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Idempotent TRUNCATE
        print("\n--- Step 2A: Resetting existing tables (TRUNCATE CASCADE) ---", flush=True)
        cur.execute("TRUNCATE TABLE standard_references, standard_lineage, licence_varieties, standards RESTART IDENTITY CASCADE;")
        conn.commit()
        print("Existing data truncated.", flush=True)

        # Print 1:1 Mapping
        mapping = [
            ("Dept", "dept", "Text"),
            ("Standard Number", "standard_number", "Text (Unique PK)"),
            ("Standard Number", "base_number", "Text (Normalized: uppercase, no spaces, no :YYYY)"),
            ("Title", "title", "Text"),
            ("Status", "status_raw", "Text"),
            ("Published On", "published_on", "Date (YYYY-MM-DD)"),
            ("Year", "year", "Integer (4-digit year)"),
            ("Reaffirmation", "reaffirmation_year", "Integer (Extracted 4-digit year)"),
            ("Revisions", "revisions_count", "Integer"),
            ("Technical Committee", "technical_committee", "Text"),
            ("ICS Code", "ics_code", "Text"),
            ("Type of Standard", "type_of_standard", "Text"),
            ("Certification", "certification", "Text"),
            ("Active Licences", "active_licences", "Integer"),
            ("CRS Count", "crs_count", "Integer"),
            ("References Count", "references_count", "Integer"),
            ("Supersedes (Older)", "supersedes_older", "Text"),
            ("Superseded By (Newer)", "superseded_by_newer", "Text"),
            ("Equivalent Standard", "equivalent_standard", "Text"),
            ("QCO / Ministry", "qco_ministry", "Text"),
            ("Source URL", "source_url", "Text"),
            ("isStatus_label", "is_status_label", "Text"),
            ("withdrawStatus", "withdraw_status", "Boolean"),
            ("Ministry", "ministry", "Text"),
            ("Group", "group_name", "Text"),
            ("SubGroup", "sub_group", "Text"),
            ("SubSubGroup", "sub_sub_group", "Text"),
            ("virtual_scope", "virtual_scope", "Text"),
            ("[Constant]", "verified", "Boolean (True)")
        ]
        print("\n1:1 Column Mapping Applied:")
        print(f"{'Excel Column':<25} -> {'Database Column':<22} | {'Type / Transformation'}")
        print("-" * 75)
        for excel_col, db_col, tr in mapping:
            print(f"{excel_col:<25} -> {db_col:<22} | {tr}")

        # Insert standards
        print("\n--- Step 2B: Inserting into 'standards' ---", flush=True)
        insert_standards_sql = """
            INSERT INTO standards (
                standard_number, base_number, year, dept, title, status_raw, is_status_label,
                withdraw_status, published_on, reaffirmation_year, revisions_count,
                technical_committee, ics_code, type_of_standard, equivalent_standard,
                certification, qco_ministry, ministry, group_name, sub_group, sub_sub_group,
                active_licences, crs_count, references_count, supersedes_older,
                superseded_by_newer, source_url, virtual_scope, verified
            ) VALUES %s;
        """
        execute_values(cur, insert_standards_sql, standards_rows, page_size=200)
        conn.commit()
        print(f"Inserted {len(standards_rows)} rows into 'standards'.", flush=True)

        # Lookup map for foreign keys
        cur.execute("SELECT standard_number, id FROM standards;")
        std_id_map = {row[0]: row[1] for row in cur.fetchall()}
        print(f"Retrieved {len(std_id_map)} standard IDs.", flush=True)

        # Insert standard_references
        print("\n--- Step 2C: Inserting into 'standard_references' ---", flush=True)
        ref_db_rows = []
        unresolved_ref_count = 0
        unresolved_refs = {}
        for src_sn, ref_sn, ref_t, ref_pk, etype, rstatus, lat_yr in raw_ref_items:
            primary_id = std_id_map.get(src_sn)
            if primary_id is None:
                unresolved_ref_count += 1
                unresolved_refs[src_sn] = unresolved_refs.get(src_sn, 0) + 1
            ref_db_rows.append((
                primary_id, src_sn, ref_sn, ref_t, ref_pk, etype, rstatus, lat_yr
            ))
        print(f"Total reference rows: {len(ref_db_rows)}", flush=True)
        print(f"Resolved primary_standard_id: {len(ref_db_rows) - unresolved_ref_count}", flush=True)
        print(f"Unresolved primary_standard_id: {unresolved_ref_count}", flush=True)
        if unresolved_refs:
            print("Unresolved breakdown (pilot crawl standards):", unresolved_refs, flush=True)

        insert_refs_sql = """
            INSERT INTO standard_references (
                primary_standard_id, primary_standard_num, ref_standard_number,
                ref_title, ref_pk_is_id, edge_type, referenced_status, latest_edition_year
            ) VALUES %s;
        """
        execute_values(cur, insert_refs_sql, ref_db_rows, page_size=500)
        conn.commit()
        print(f"Inserted {len(ref_db_rows)} rows into 'standard_references'.", flush=True)

        # Insert standard_lineage
        print("\n--- Step 2D: Inserting into 'standard_lineage' ---", flush=True)
        lineage_db_rows = []
        for sn, rel, raw_p, b, y in raw_lineage_items:
            std_id = std_id_map.get(sn)
            lineage_db_rows.append((
                std_id, sn, rel, raw_p, b, y
            ))
        insert_lineage_sql = """
            INSERT INTO standard_lineage (
                standard_id, standard_number, relationship, related_standard_raw,
                related_base_number, related_year
            ) VALUES %s;
        """
        execute_values(cur, insert_lineage_sql, lineage_db_rows, page_size=200)
        conn.commit()
        print(f"Inserted {len(lineage_db_rows)} rows into 'standard_lineage'.", flush=True)

        # Insert licence_varieties
        print("\n--- Step 2E: Inserting into 'licence_varieties' ---", flush=True)
        lic_db_rows = []
        for sn, tot, pv in raw_lic_items:
            std_id = std_id_map.get(sn)
            lic_db_rows.append((
                std_id, sn, tot, pv
            ))
        insert_lic_sql = """
            INSERT INTO licence_varieties (
                standard_id, standard_number, total_isi_licences, product_varieties
            ) VALUES %s;
        """
        execute_values(cur, insert_lic_sql, lic_db_rows, page_size=100)
        conn.commit()
        print(f"Inserted {len(lic_db_rows)} rows into 'licence_varieties'.", flush=True)

        print("\n=======================================================", flush=True)
        print("ALL DATA LOADED AND COMMITTED TO SUPABASE SUCCESSFULLY!", flush=True)
        print("=======================================================", flush=True)

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: Database transaction aborted: {e}", flush=True)
        raise e
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
