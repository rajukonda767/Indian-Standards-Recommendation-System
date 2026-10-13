"""
migrations/run_migration.py
===========================
Simple psycopg2 migration runner.
Usage: python migrations/run_migration.py 001_audit_tables.sql
"""
import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from app.db import init_db_pool, get_db_cursor

def run(sql_filename: str) -> None:
    sql_path = os.path.join(os.path.dirname(__file__), sql_filename)
    if not os.path.exists(sql_path):
        logger.error(f"File not found: {sql_path}")
        sys.exit(1)

    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read()

    init_db_pool()

    # Strip single-line comments before splitting (handles comments containing ';')
    lines = [l for l in sql.splitlines() if not l.strip().startswith('--')]
    sql_stripped = '\n'.join(lines)

    # Split on semicolons; skip empty statements
    statements = [s.strip() for s in sql_stripped.split(';') if s.strip()]

    logger.info(f"Running migration: {sql_filename} ({len(statements)} statements)")
    with get_db_cursor() as cur:
        for i, stmt in enumerate(statements, 1):
            try:
                cur.execute(stmt)
                logger.info(f"  [{i}/{len(statements)}] OK: {stmt[:60].replace(chr(10), ' ')}...")
            except Exception as e:
                logger.error(f"  [{i}/{len(statements)}] FAILED: {e}")
                logger.error(f"  Statement was: {stmt[:200]}")
                sys.exit(1)

    logger.info(f"Migration '{sql_filename}' completed successfully.")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: python migrations/run_migration.py <filename.sql>")
        sys.exit(1)
    run(sys.argv[1])
