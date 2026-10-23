"""Run all SQL schema files in backend/sql/ to initialize PostgreSQL tables."""
import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")
url = os.getenv("DATABASE_URL")

if not url:
    raise SystemExit("DATABASE_URL is missing in backend/.env")

sql_files = sorted(Path("backend/sql").glob("*.sql"))

with psycopg.connect(url) as conn:
    for f in sql_files:
        print(f"Applying schema: {f.name}")
        conn.execute(f.read_text(encoding="utf-8"))
    conn.commit()

    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    ).fetchall()

print("-" * 40)
print("Active tables in database:", [t[0] for t in tables])
