import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database.db"


def using_postgres() -> bool:
    url = os.environ.get("DATABASE_URL")
    return bool(url) and not url.startswith("sqlite")


@contextmanager
def db_conn():
    """Yield a DB connection.

    - If DATABASE_URL is set (non-sqlite), connect to Postgres.
    - Else use local SQLite database.db.
    """
    if using_postgres():
        import psycopg2
        import psycopg2.extras

        try:
            conn = psycopg2.connect(
                os.environ["DATABASE_URL"],
                cursor_factory=psycopg2.extras.RealDictCursor,
                connect_timeout=5,
            )
        except psycopg2.OperationalError:
            # Fallback to SQLite if Postgres is unreachable (e.g., IPv6-only network).
            conn = None

        if conn is not None:
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()
            return

    # SQLite fallback
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def exec_sql(conn, sql: str, params=None):
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
        return cur
    finally:
        try:
            cur.close()
        except Exception:
            pass
