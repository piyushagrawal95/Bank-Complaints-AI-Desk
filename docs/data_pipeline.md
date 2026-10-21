# Data Loading and Ingestion Pipeline

## 1. CFPB Complaints Streaming Loader (`scripts/load_complaints.py`)

- **Dataset Scale**: Millions of consumer complaints from the Consumer Financial Protection Bureau.
- **Memory Safety**: Uses Pandas `chunksize=5000` to stream CSV records in batches. Memory overhead remains strictly constant (<200MB) regardless of file size.
- **Sanitization Strategy**:
  - Null coercion for non-mandatory metadata columns.
  - Strict date normalization (`UTC format="mixed"`).
  - Skips corrupted rows lacking primary keys or required categories, logging exact reasons per chunk.
  - Idempotent PostgreSQL loading via `ON CONFLICT (complaint_id) DO NOTHING`.

---

## 2. Regulation PDF RAG Ingestion Pipeline (`scripts/ingest_regulations.py`)

- **Document Source**: Official 12 CFR Part 1005 (Regulation E - Electronic Fund Transfers, 182 pages).
- **Chunking Strategy**:
  - Dynamic CFR Section Header tracking (`§ 1005.11 Error Resolution`, etc.).
  - Sliding text window of 900 characters with 150-character overlap to preserve semantic continuity across sentences.
  - Attaches source PDF page number to every text segment.
- **Embedding Pipeline**:
  - Local ONNX embedding inference with `BAAI/bge-small-en-v1.5` (384 dimensions).
  - Batching: 64 chunks per vectorization pass.
  - Indexed in PostgreSQL with HNSW for sub-10ms nearest-neighbor queries.
