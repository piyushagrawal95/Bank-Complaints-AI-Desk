"""Chunked, memory-safe data loader for CFPB complaints dataset."""
import argparse
import os
import pandas as pd
import psycopg
from dotenv import load_dotenv

COLUMNS = {
    "Complaint ID": "complaint_id",
    "Date received": "date_received",
    "Product": "product",
    "Sub-product": "sub_product",
    "Issue": "issue",
    "Sub-issue": "sub_issue",
    "Consumer complaint narrative": "narrative",
    "Company public response": "company_public_response",
    "Company": "company",
    "State": "state",
    "ZIP code": "zip_code",
    "Tags": "tags",
    "Submitted via": "submitted_via",
    "Date sent to company": "date_sent_to_company",
    "Company response to consumer": "company_response_to_consumer",
    "Timely response?": "timely_response",
}
DB_COLUMNS = list(COLUMNS.values())
REQUIRED = ["complaint_id", "date_received", "product", "issue", "company"]
OPTIONAL_CSV_COLUMNS = {"Consumer complaint narrative"}

INSERT_SQL = (
    f"INSERT INTO complaints ({', '.join(DB_COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(DB_COLUMNS))}) "
    "ON CONFLICT (complaint_id) DO UPDATE SET "
    "narrative = COALESCE(EXCLUDED.narrative, complaints.narrative)"
)


def clean(chunk):
    chunk = chunk.rename(columns=COLUMNS)
    for col in DB_COLUMNS:
        if col not in chunk.columns:
            chunk[col] = None
    chunk = chunk[DB_COLUMNS].copy()

    chunk["complaint_id"] = chunk["complaint_id"].astype(str).str.replace(r"[^\d]", "", regex=True)
    chunk["complaint_id"] = pd.to_numeric(chunk["complaint_id"], errors="coerce")
    for col in ["date_received", "date_sent_to_company"]:
        chunk[col] = pd.to_datetime(
            chunk[col], errors="coerce", utc=True, format="mixed"
        ).dt.date
    chunk["timely_response"] = chunk["timely_response"].map({"Yes": True, "No": False})

    reasons = {col: int(chunk[col].isna().sum()) for col in REQUIRED}
    bad = chunk[REQUIRED].isna().any(axis=1)
    skipped = int(bad.sum())
    chunk = chunk[~bad].copy()
    chunk["complaint_id"] = chunk["complaint_id"].astype("int64")

    chunk = chunk.astype(object).where(chunk.notna(), None)
    rows = list(chunk.itertuples(index=False, name=None))
    return rows, skipped, reasons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", default="data/complaints/complaints-2026-10-14_02_31.csv")
    parser.add_argument("--chunksize", type=int, default=5000)
    args = parser.parse_args()

    load_dotenv("backend/.env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is empty in backend/.env")

    header = list(pd.read_csv(args.csv_path, nrows=0).columns)
    print("CSV columns found:", len(header))

    total_read = total_skipped = total_inserted = failed_chunks = 0

    with psycopg.connect(url) as conn:
        reader = pd.read_csv(args.csv_path, dtype=str, chunksize=args.chunksize)
        for i, chunk in enumerate(reader, start=1):
            total_read += len(chunk)
            try:
                rows, skipped, reasons = clean(chunk)
                with conn.cursor() as cur:
                    cur.executemany(INSERT_SQL, rows)
                    inserted = cur.rowcount
                conn.commit()
            except Exception as exc:
                conn.rollback()
                failed_chunks += 1
                print(f"Chunk {i} failed: {exc}")
                continue
            total_skipped += skipped
            total_inserted += inserted
            print(f"Chunk {i}: read {len(chunk)}, inserted {inserted}, skipped {skipped}")

        count = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]

    print("-" * 40)
    print(f"Total Rows Read:     {total_read}")
    print(f"Total Rows Inserted: {total_inserted}")
    print(f"Total in Database:   {count}")


if __name__ == "__main__":
    main()
