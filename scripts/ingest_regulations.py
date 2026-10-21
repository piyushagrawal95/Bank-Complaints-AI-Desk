"""
Extract, dynamically chunk (4% size, 15% overlap), and embed
official banking regulations (E, F, V, Z) into pgvector.
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastembed import TextEmbedding
import psycopg
import pypdf

load_dotenv("backend/.env")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL is missing in backend/.env")

REGULATION_DIR = Path("data/regulations")

# All 4 Federal Banking Regulations mapping
REGULATIONS = [
    {
        "file": "Regulation_E.pdf",
        "name": "Regulation E (12 CFR Part 1005) - Electronic Fund Transfers",
        "part": "1005",
    },
    {
        "file": "Regulation F.pdf",
        "name": "Regulation F (12 CFR Part 1006) - Debt Collection",
        "part": "1006",
    },
    {
        "file": "Regulation V.pdf",
        "name": "Regulation V (12 CFR Part 1022) - Fair Credit Reporting",
        "part": "1022",
    },
    {
        "file": "Regulation Z.pdf",
        "name": "Regulation Z (12 CFR Part 1026) - Truth in Lending & Credit Cards",
        "part": "1026",
    },
]

# -------------------------------------------------------------
# PERCENTAGE-BASED DYNAMIC CHUNKING PARAMETERS (Sir's Formula)
# -------------------------------------------------------------
CHUNK_PCT = 0.20       # 20% of text as base target chunk size
OVERLAP_PCT = 0.15     # 15% of chunk size as dynamic overlap
MIN_CHUNK_CHARS = 400  # Safety minimum length
MAX_CHUNK_CHARS = 1200 # Safety maximum length for embedding model
BATCH_SIZE = 64


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.replace("\u00a0", " ").strip()


def percent_dynamic_chunk(text: str, chunk_pct: float = CHUNK_PCT, overlap_pct: float = OVERLAP_PCT) -> list[str]:
    """
    Percentage-Based Dynamic Chunking:
    - Target Chunk Size = 20% of total text length.
    - Dynamic Overlap = 15% of the calculated chunk size.
    - Sentence Boundary Snapping: Cut hamesha full-stop (. ! ?) par lagta hai.
    """
    text_len = len(text)
    if text_len < 100:
        return [text] if text_len >= 50 else []

    # 1. Calculate 4% target size with bounds
    raw_size = int(text_len * chunk_pct)
    chunk_size = max(MIN_CHUNK_CHARS, min(raw_size, MAX_CHUNK_CHARS))

    # 2. Calculate 15% dynamic overlap
    overlap = int(chunk_size * overlap_pct)
    step = chunk_size - overlap

    chunks = []
    start = 0

    while start < text_len:
        target_end = min(start + chunk_size, text_len)

        # Sentence Boundary Snapping (Full stop par cleanly cut karna)
        if target_end < text_len:
            window_start = max(start + MIN_CHUNK_CHARS, target_end - 120)
            window_end = min(text_len, target_end + 120)
            matches = list(re.finditer(r'(?<=[.!?])\s+', text[window_start:window_end]))
            if matches:
                best_match = min(matches, key=lambda m: abs((window_start + m.end()) - target_end))
                actual_end = window_start + best_match.end()
            else:
                actual_end = target_end
        else:
            actual_end = text_len

        chunk_str = text[start:actual_end].strip()
        if len(chunk_str) >= 80:
            chunks.append(chunk_str)

        if actual_end >= text_len:
            break

        # Move forward maintaining 15% dynamic overlap
        start = actual_end - overlap

    return chunks


def extract_chunks(pdf_path: Path, reg_name: str, part_num: str):
    reader = pypdf.PdfReader(str(pdf_path))
    chunks = []
    current_section = f"12 CFR Part {part_num} - General"

    print(f"\n📖 Reading {len(reader.pages)} pages from {pdf_path.name}...")
    for page_idx, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        if not raw_text.strip():
            continue

        # Dynamic Section Tracking (§ 1005.xx, § 1006.xx, § 1022.xx, § 1026.xx)
        section_match = re.search(
            rf"(?:§|\u00a7|\ufffd)?\s*({part_num}\.\d+\s+[A-Za-z\s,-]{{3,40}})",
            raw_text,
        )
        if section_match:
            detected = "§ " + " ".join(section_match.group(1).split()[:6])
            if len(detected) > 8:
                current_section = detected

        cleaned_page = clean_text(raw_text)

        # Apply 4% Chunking with 15% Dynamic Overlap
        page_chunks = percent_dynamic_chunk(cleaned_page, CHUNK_PCT, OVERLAP_PCT)
        for chunk_str in page_chunks:
            chunks.append({
                "regulation_name": reg_name,
                "section": current_section,
                "page_number": page_idx,
                "chunk_text": chunk_str,
            })

    return chunks


def ingest_regulation(reg_info, embed_model, conn):
    pdf_path = REGULATION_DIR / reg_info["file"]
    if not pdf_path.exists():
        print(f"⚠️ Warning: File not found: {pdf_path.name}, skipping.")
        return 0

    chunks = extract_chunks(pdf_path, reg_info["name"], reg_info["part"])
    print(f"   ✂️ Generated {len(chunks)} dynamic chunks (4% size, 15% overlap).")

    print(f"   🧠 Generating vector embeddings for {reg_info['file']}...")
    chunk_texts = [f"{c['section']}: {c['chunk_text']}" for c in chunks]
    embeddings = list(embed_model.embed(chunk_texts, batch_size=BATCH_SIZE))

    print(f"   💾 Storing in PostgreSQL (pgvector)...")
    with conn.cursor() as cur:
        # Purana data delete karte hain taaki duplicate na ho
        cur.execute(
            "DELETE FROM regulation_chunks WHERE regulation_name = %s",
            [reg_info["name"]],
        )

        insert_sql = """
            INSERT INTO regulation_chunks (regulation_name, section, page_number, chunk_text, embedding)
            VALUES (%s, %s, %s, %s, %s)
        """
        rows = [
            (
                c["regulation_name"],
                c["section"],
                c["page_number"],
                c["chunk_text"],
                emb.tolist() if hasattr(emb, "tolist") else list(emb),
            )
            for c, emb in zip(chunks, embeddings)
        ]
        cur.executemany(insert_sql, rows)
        conn.commit()

    count = conn.execute(
        "SELECT COUNT(*) FROM regulation_chunks WHERE regulation_name = %s",
        [reg_info["name"]],
    ).fetchone()[0]

    print(f"   ✅ Successfully indexed {count} dynamic chunks for {reg_info['file']}!")
    return count


def main():
    print("=" * 60)
    print("BANKING REGULATIONS RAG INGESTION PIPELINE")
    print("Percentage Dynamic Chunking: 4% Size, 15% Overlap")
    print("=" * 60)

    print("Loading FastEmbed model (BAAI/bge-small-en-v1.5)...")
    embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    total_chunks = 0
    with psycopg.connect(DATABASE_URL) as conn:
        for reg in REGULATIONS:
            total_chunks += ingest_regulation(reg, embed_model, conn)

        final_total = conn.execute("SELECT COUNT(*) FROM regulation_chunks").fetchone()[0]

    print("\n" + "=" * 60)
    print(f"🎉 INGESTION COMPLETE! Total Regulation Chunks in DB: {final_total}")
    print("=" * 60)


if __name__ == "__main__":
    main()