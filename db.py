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

    Important: when DATABASE_URL is set, do NOT silently fall back to SQLite.
    That creates a split-brain where /submit writes to Postgres but /admin reads from SQLite.
    """
    if using_postgres():
        import time
        import psycopg2
        import psycopg2.extras

        last_exc = None
        for _ in range(3):
            try:
                conn = psycopg2.connect(
                    os.environ["DATABASE_URL"],
                    cursor_factory=psycopg2.extras.RealDictCursor,
                    connect_timeout=5,
                )
                last_exc = None
                break
            except psycopg2.OperationalError as e:
                last_exc = e
                time.sleep(0.5)

        if last_exc is not None:
            raise last_exc

        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
        return

    # SQLite (only when Postgres is not configured)
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
