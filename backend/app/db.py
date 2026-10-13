"""
db.py
=====
Thread-safe PostgreSQL connection pooling for Supabase with automatic keep-alive.
"""

import time
import logging
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from app.config import settings

logger = logging.getLogger(__name__)

_pool = None

def init_db_pool(minconn: int = 3, maxconn: int = 10):
    global _pool
    if _pool is None:
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL is not configured in settings.")
        _pool = pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            dsn=settings.DATABASE_URL,
            connect_timeout=15,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )
        # Pre-warm all minconn connections to avoid runtime TLS handshakes
        try:
            conns = [_pool.getconn() for _ in range(minconn)]
            for c in conns:
                with c.cursor() as cur:
                    cur.execute("SELECT 1;")
                _pool.putconn(c)
            logger.info(f"Database connection pool initialized and pre-warmed {minconn} connections successfully.")
        except Exception as e:
            logger.warning(f"Connection pre-warm warning: {e}")
    return _pool

def close_db_pool():
    global _pool
    if _pool is not None:
        logger.info("Closing database connection pool...")
        _pool.closeall()
        _pool = None

@contextmanager
def get_db_cursor():
    """
    Context manager to borrow a connection from the pool,
    yield a cursor, and safely return the connection.
    Automatically validates liveness and evicts broken/dropped connections.
    """
    global _pool
    if _pool is None:
        init_db_pool()
    
    t0 = time.perf_counter()
    conn = _pool.getconn()
    checkout_ms = (time.perf_counter() - t0) * 1000.0
    if checkout_ms > 200.0:
        logger.warning(f"DB checkout high latency: {checkout_ms:.1f}ms")

    # Validate connection liveness; if dead, discard and get a fresh connection
    if conn.closed:
        _pool.putconn(conn, close=True)
        conn = _pool.getconn()

    conn.autocommit = True
    try:
        with conn.cursor() as test_cur:
            test_cur.execute("SELECT 1;")
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        try:
            _pool.putconn(conn, close=True)
        except Exception:
            pass
        conn = _pool.getconn()
        conn.autocommit = True
    broken = False
    try:
        with conn.cursor() as cur:
            yield cur
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
        broken = True
        logger.warning(f"Evicting broken DB connection from pool: {e}")
        raise
    finally:
        try:
            _pool.putconn(conn, close=broken)
        except Exception:
            pass
