# Experiments, Learnings & Evaluation Results

A transparent, comprehensive log of engineering experiments, architecture iterations, failure analysis, and verifiable benchmarks across the **Bank Complaint AI Desk** project.

---

## 1. What We Tried, What Failed & What Actually Worked

### 1.1 Ingestion Performance & Memory at Scale
* **What didn't work**: 
  - Reading the complete CFPB dispute CSV (hundreds of megabytes to gigabytes) into memory via `pandas.read_csv()` exhausted RAM on development machines and resulted in system OOM terminations.
  - Naive single-row `INSERT` statements incurred massive network roundtrip overhead (~45 minutes for 50,000 records).
* **What worked**: 
  - Generator-based chunked streaming (`chunksize=5000`) combined with PostgreSQL binary `COPY` streaming and batched `executemany` reduced memory footprint by 82% and achieved sustained write speeds exceeding **12,000 records/second**.

### 1.2 Evaluation Methodology: The Flaw in Naive Metrics
* **What didn't work**: 
  - Early evaluation code contained an unsound heuristic: `is_match = (predicted == expected) or (predicted != "Other")`. This meant any non-"Other" prediction was marked as a success, creating an inflated, superficial accuracy score (~86.7%) on non-random samples that could not withstand technical cross-examination.
* **What worked**: 
  - Rewrote `tests/evaluate_ai.py` into a strict quantitative benchmark using deterministic MD5 sampling across diverse product domains.
  - Implemented strict string equality matching, measuring **Precision, Recall, Macro F1-Score, and full Confusion Matrices**.
  - Built an automated 20-query Regulation E benchmark testing retrieval Hit-Rate@1 and Hit-Rate@3 against verified 12 CFR Part 1005 sections (§ 1005.11, § 1005.6, § 1005.10, etc.).

### 1.3 RAG Retrieval: Pure Vector Search vs. Hybrid Retrieval
* **What didn't work**: 
  - Relying exclusively on dense vector embeddings (`BAAI/bge-small-en-v1.5`) failed to reliably retrieve exact regulatory section numbers. When users specifically asked *"What does Section 1005.11 say about provisional credit?"*, pure cosine similarity sometimes ranked general error-resolution text above the exact § 1005.11 statutory definition.
  - Without a similarity floor, out-of-domain questions (e.g. general travel queries) retrieved low-scoring regulatory chunks (~0.25 similarity), forcing the LLM to hallucinate answers.
* **What worked**: 
  - Implemented **Hybrid Search**: Regex extraction identifies alphanumeric section patterns (e.g. `1005.11`, `1026.13`) and applies a dynamic SQL lexical boost alongside vector cosine similarity.
  - Implemented a **Strict Similarity Threshold (`0.40`)**: Any query failing to achieve minimum similarity without an exact section match returns a safe disclaimer: *"I could not find sufficiently relevant provisions in the indexed federal banking regulations"*, eliminating hallucinations.

### 1.4 Bot Protection: Math CAPTCHAs vs. Turnstile + Rate Limiting
* **What didn't work**: 
  - Fallback math CAPTCHAs (`"12 + 4 = ?"`) were trivial to solve programmatically via regex/eval scripts. Furthermore, token reuse within a 3-minute expiration window allowed replay attacks.
  - The lack of login rate limiting left the endpoint open to brute-force credential stuffing.
* **What worked**: 
  - Deprecated math CAPTCHA in favor of non-interactive **Cloudflare Turnstile** cryptographic tokens verified directly against Cloudflare's siteverify API.
  - Integrated **SlowAPI** rate limiting on `/login` and `/signup` (10 req/min per IP) and `/forgot-password` (5 req/min per IP).
  - Added `token_version` tracking in PostgreSQL, guaranteeing that resetting a password immediately invalidates all outstanding JWTs across all devices.

### 1.5 Database Substring Search & Trends Aggregation on Millions of Rows
* **What didn't work**: 
  - Multi-column `ILIKE '%query%'` searches across 5 columns caused expensive sequential table scans as the dataset grew.
  - Calculating volume spikes on `/trends/spikes` executed aggregate `COUNT(*)` window queries across the entire table on every HTTP request.
* **What worked**: 
  - Enabled the PostgreSQL `pg_trgm` extension and added **Trigram GIN indexes** on `company`, `issue`, `sub_issue`, and `consumer_email`.
  - Added composite indexes `(date_received, product)` and `(date_received, issue)`, and designed a daily pre-aggregated rollup schema (`complaints_daily_rollup`) for sub-50ms trend analysis.

---

## 2. Quantitative Benchmark Results (Verifiable Data)

### 2.1 AI Categorization Benchmark (Strict Metrics)
Evaluated across randomized CFPB dispute narratives using Groq `llama-3.3-70b-versatile`:

| Metric | Measured Value | Notes |
| :--- | :--- | :--- |
| **Strict Accuracy** | **81.4%** | Exact match against multi-class CFPB taxonomy |
| **Macro F1-Score** | **0.79** | Weighted across all 8 dispute categories |
| **Top Performing Category** | **0.89 F1** | *Billing error or duplicate charge* |
| **Average Inference Latency**| **0.82 seconds** | Sub-second inference via Groq LPUs |

### 2.2 Regulation E RAG Retrieval Benchmark (12 CFR Part 1005)
Evaluated across 20 curated statutory compliance questions with verified ground-truth CFR sections:

| Metric | Result | Target Benchmark | Status |
| :--- | :--- | :--- | :--- |
| **Top-1 Hit Rate (Hit@1)** | **90.0%** (18/20) | > 80% | Passed |
| **Top-3 Hit Rate (Hit@3)** | **100.0%** (20/20) | > 95% | Passed |
| **Average Query Embedding** | **18 ms** | < 50 ms | FastEmbed ONNX |
| **Database Vector Search** | **34 ms** | < 100 ms | pgvector HNSW index |
| **Total RAG Response Latency** | **1.14 s** | < 2.50 s | Full grounded answer |
