"""
Database configuration and connection management
"""
import os
import psycopg2
import psycopg2.extras
import psycopg2.pool
from contextlib import contextmanager

# Load .env for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Load Streamlit Cloud secrets into environment
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        for key in ["DATABASE_URL", "GROQ_API_KEY",
                    "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
                    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS"]:
            if key in st.secrets and not os.environ.get(key):
                os.environ[key] = str(st.secrets[key])
except Exception:
    pass

DATABASE_URL = os.getenv("DATABASE_URL")


# ── FIX 1: Connection pool — created once, reused across all queries ──────────
@st.cache_resource
def get_pool():
    if DATABASE_URL:
        return psycopg2.pool.SimpleConnectionPool(
            1, 5, DATABASE_URL, connect_timeout=10
        )
    else:
        return psycopg2.pool.SimpleConnectionPool(
            1, 5,
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "postgres"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            connect_timeout=10,
        )


@contextmanager
def get_db():
    """Borrow connection from pool, return it after use instead of closing."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)  # return to pool, not close


# ── FIX 2: init_db runs only once per app session, not on every rerun ─────────
_db_initialized = False

def init_db():
    global _db_initialized
    if _db_initialized:
        return  # skip if already ran this session
    try:
        base_dir    = os.path.dirname(__file__)
        schema_path = os.path.join(base_dir, "../database/schema.sql")
        with get_db() as conn:
            with conn.cursor() as cur:
                with open(schema_path, "r") as f:
                    cur.execute(f.read())
        print("[DB] ✅ Schema applied.")
    except Exception as e:
        print(f"[DB] ⚠️ Init warning: {e}")
    finally:
        _db_initialized = True  # never retry, even on error


def execute_query(query: str, params=None, fetch=True):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            if fetch and cur.description:
                return [dict(row) for row in cur.fetchall()]
            return []


def execute_one(query: str, params=None):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            if cur.description:
                row = cur.fetchone()
                return dict(row) if row else None
    return None


def execute_insert(query: str, params=None):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            if cur.description:
                row = cur.fetchone()
                return dict(row) if row else None
    return None