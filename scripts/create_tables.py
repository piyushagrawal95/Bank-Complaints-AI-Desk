"""Run all SQL schema files in backend/sql/ to initialize PostgreSQL tables in proper dependency order."""
import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / "backend" / ".env")
url = os.getenv("DATABASE_URL")

if not url:
    raise SystemExit("DATABASE_URL is missing in backend/.env")

sql_dir = project_root / "backend" / "sql"
if not sql_dir.exists():
    raise SystemExit(f"SQL directory not found: {sql_dir}")

# Explicit dependency execution order to satisfy foreign keys and vector extensions
ORDERED_FILES = [
    "create_users.sql",
    "create_complaints.sql",
    "create_regulations.sql",
    "create_complaint_embeddings.sql",
    "create_complaints_analysis.sql",
    "create_complaint_responses.sql",
    "create_role_upgrade_requests.sql",
    "create_password_resets.sql",
]

all_sql_files = {f.name: f for f in sql_dir.glob("*.sql")}
sql_files_to_run = []

# First add explicitly ordered files
for fname in ORDERED_FILES:
    if fname in all_sql_files:
        sql_files_to_run.append(all_sql_files.pop(fname))

# Then add any remaining SQL files
for fname in sorted(all_sql_files.keys()):
    sql_files_to_run.append(all_sql_files[fname])

with psycopg.connect(url) as conn:
    # Ensure pgvector extension is available
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    for f in sql_files_to_run:
        print(f"Applying schema: {f.name}")
        conn.execute(f.read_text(encoding="utf-8"))
    conn.commit()

    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    ).fetchall()

print("-" * 40)
print("Active tables in database:", [t[0] for t in tables])
