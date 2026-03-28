"""
Database configuration and connection management
"""
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# Load Streamlit Cloud secrets into environment
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        for key in ["DATABASE_URL", "GROQ_API_KEY", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]:
            if key in st.secrets and not os.environ.get(key):
                os.environ[key] = str(st.secrets[key])
except Exception:
    pass

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode="require")
    else:
        return psycopg2.connect(
            host     = os.getenv("DB_HOST", "localhost"),
            port     = os.getenv("DB_PORT", "5432"),
            database = os.getenv("DB_NAME", "postgres"),
            user     = os.getenv("DB_USER", "postgres"),
            password = os.getenv("DB_PASSWORD", ""),
            sslmode  = "require"
        )


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize schema and run migrations on every startup."""
    base_dir     = os.path.dirname(__file__)
    schema_path  = os.path.join(base_dir, "../database/schema.sql")
    migrate_path = os.path.join(base_dir, "../database/migrate.sql")

    with get_db() as conn:
        with conn.cursor() as cur:
            with open(schema_path, "r") as f:
                cur.execute(f.read())
            if os.path.exists(migrate_path):
                with open(migrate_path, "r") as f:
                    cur.execute(f.read())

    print("[DB] ✅ Schema and migrations applied.")


def execute_query(query: str, params=None, fetch=True):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch and cur.description:
                return [dict(row) for row in cur.fetchall()]
            return []


def execute_one(query: str, params=None):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                row = cur.fetchone()
                return dict(row) if row else None
    return None


def execute_insert(query: str, params=None):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                row = cur.fetchone()
                return dict(row) if row else None
    return None