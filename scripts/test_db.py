import os
import psycopg
from dotenv import load_dotenv

from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")
url = os.getenv("DATABASE_URL")

if not url:
    raise SystemExit("DATABASE_URL is empty in backend/.env")

with psycopg.connect(url) as conn:
    print("PostgreSQL Version:", conn.execute("SELECT version();").fetchone()[0])
    has_vector = conn.execute("SELECT extname FROM pg_extension WHERE extname='vector';").fetchone()
    print("pgvector Extension Active:", bool(has_vector))
