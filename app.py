import os
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from db import db_conn, exec_sql, using_postgres

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"

ADMIN_PATH = "/admin226"  # per spec

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB


def init_db():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with db_conn() as conn:
        # If DATABASE_URL is set but Postgres is unreachable, db_conn() may fall back to SQLite.
        # In that case, don't create a SQLite schema by accident; we'll retry later.
        if using_postgres() and conn.__class__.__module__.startswith("sqlite3"):
            return

        # Create schema (SQLite vs Postgres)
        if using_postgres():
            exec_sql(
                conn,
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image TEXT,
                    time TEXT NOT NULL,
                    service_attitude INTEGER,
                    food_quality TEXT,
                    overall_rating TEXT
                )
                """,
            )
        else:
            exec_sql(
                conn,
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image TEXT,
                    time TEXT NOT NULL,
                    service_attitude INTEGER,
                    food_quality TEXT,
                    overall_rating TEXT
                )
                """,
            )

        # SQLite migration (Postgres doesn't support PRAGMA)
        try:
            cur = exec_sql(conn, "PRAGMA table_info(messages)")
            cols = {row[1] for row in cur.fetchall()}
            if "service_attitude" not in cols:
                exec_sql(conn, "ALTER TABLE messages ADD COLUMN service_attitude INTEGER")
            if "food_quality" not in cols:
                exec_sql(conn, "ALTER TABLE messages ADD COLUMN food_quality TEXT")
            if "overall_rating" not in cols:
                exec_sql(conn, "ALTER TABLE messages ADD COLUMN overall_rating TEXT")
        except Exception:
            # Likely Postgres; ignore
            pass


def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


# Ensure DB + schema exist even when running under WSGI servers (gunicorn)
# Do not crash the whole app if the external DB is temporarily unreachable.
try:
    init_db()
except Exception as e:
    # Keep app running; admin page will show empty until DB is reachable.
    print(f"[WARN] init_db failed: {e}")


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/submit")
def submit():
    # Ensure schema exists (in case the app started while DB was unreachable)
    try:
        init_db()
    except Exception as e:
        print(f"[WARN] init_db in submit failed: {e}")
    category = (request.form.get("category") or "").strip()
    content = (request.form.get("content") or "").strip()

    service_attitude_raw = (request.form.get("service_attitude") or "").strip()
    food_quality = (request.form.get("food_quality") or "").strip()
    overall_rating = (request.form.get("overall_rating") or "").strip()

    # 分类固定为“炸串”
    if category != "炸串":
        category = "炸串"

    if not content:
        flash("留言内容不能为空")
        return redirect(url_for("index"))

    # Survey validation
    try:
        service_attitude = int(service_attitude_raw)
    except ValueError:
        service_attitude = None

    if service_attitude not in {0, 20, 60, 100}:
        flash("请选择：服务态度（0 / 20 / 60 / 100）")
        return redirect(url_for("index"))

    if food_quality not in {"难吞", "还行", "好吃", "超级好吃"}:
        flash("请选择：食物品质（难吞 / 还行 / 好吃 / 超级好吃）")
        return redirect(url_for("index"))

    if overall_rating not in {"饿死都不来", "偶尔会来", "天天都来"}:
        flash("请选择：综合评分（饿死都不来 / 偶尔会来 / 天天都来）")
        return redirect(url_for("index"))

    image_rel = None
    file = request.files.get("image")
    if file and file.filename:
        if not allowed_file(file.filename):
            flash("图片格式不支持，请上传 png/jpg/jpeg/gif/webp")
            return redirect(url_for("index"))

        filename = secure_filename(file.filename)
        # Avoid collisions
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        stem, dot, ext = filename.rpartition(".")
        safe_name = f"{stem[:50]}_{ts}.{ext.lower()}" if dot else f"upload_{ts}"

        save_path = UPLOAD_DIR / safe_name
        file.save(save_path)
        image_rel = f"uploads/{safe_name}"  # stored relative to /static

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_conn() as conn:
        # Use ? placeholders for sqlite, %s for postgres
        sql_sqlite = (
            """
            INSERT INTO messages (category, content, image, time, service_attitude, food_quality, overall_rating)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        )
        sql_pg = (
            """
            INSERT INTO messages (category, content, image, time, service_attitude, food_quality, overall_rating)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
        )
        if using_postgres():
            exec_sql(conn, sql_pg, (category, content, image_rel, now, service_attitude, food_quality, overall_rating))
        else:
            exec_sql(conn, sql_sqlite, (category, content, image_rel, now, service_attitude, food_quality, overall_rating))

    flash("提交成功，谢谢你的留言！")
    return redirect(url_for("index"))


@app.get(ADMIN_PATH)
def admin():
    # Ensure schema exists (in case the app started while DB was unreachable)
    try:
        init_db()
    except Exception as e:
        print(f"[WARN] init_db in admin failed: {e}")
    with db_conn() as conn:
        sql = (
            """
            SELECT id, category, content, image, time, service_attitude, food_quality, overall_rating
            FROM messages
            ORDER BY id DESC
            """
        )
        try:
            rows = exec_sql(conn, sql).fetchall()
        except Exception:
            rows = []
    return render_template("admin.html", rows=rows, admin_path=ADMIN_PATH)


if __name__ == "__main__":
    # Development run (use run_prod.py for stable server)
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
