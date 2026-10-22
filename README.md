# Bank Complaint AI Desk

AI-powered Complaint Intelligence & Regulatory Compliance System for Banks (CFPB Complaints + Regulation E RAG).

## Features
- **Large Dataset Ingestion**: Streams millions of CFPB complaint records using memory-efficient chunking.
- **Fast Filtered Search**: Full-text and multi-parameter filtering (by product, company, state, dates).
- **AI Categorization & Summarization**: Classifies issues into banking categories and generates 2-sentence executive summaries with PostgreSQL caching.
- **"Ask the Rules" RAG System**: Natural-language query interface against official federal banking rulebooks (Regulation E - 12 CFR Part 1005) with exact CFR section and PDF page citations using `pgvector` HNSW indexing.
- **Similar Past Cases & AI Reply Drafting**: Vector search to retrieve past resolved complaints and draft compliant response letters for human approval.
- **Trends & Volume Spike Detection**: Anomaly detection comparing rolling window traffic against historical baselines with supervisor alerts.
- **Full Authentication & RBAC**: Scrypt password hashing, JWT tokens, email-based password reset, and role enforcement (`agent`, `supervisor`, `admin`).
- **Switchable AI Models**: Change between Groq and OpenAI via `.env` settings without modifying code.

---

## Quick Start

### Backend
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python ..\scripts\create_tables.py
uvicorn app.main:app --reload
```
Runs at: `http://127.0.0.1:8000` (API Docs: `http://127.0.0.1:8000/docs`)

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Runs at: `http://localhost:5173`

---

## Detailed Documentation
A comprehensive technical report covering all requirements, technology justifications, system architecture, benchmarks, and learnings is available in **[`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md)**.

Additional modular documents are located in the [`docs/`](docs/) directory:
- [**`PROJECT_DOCUMENTATION.md`**](PROJECT_DOCUMENTATION.md): **Master Comprehensive Technical & Architecture Report**
- [`docs/setup.md`](docs/setup.md): Complete setup guide
- [`docs/architecture.md`](docs/architecture.md): System architecture and design choices
- [`docs/api.md`](docs/api.md): Full API specification
- [`docs/data_pipeline.md`](docs/data_pipeline.md): Data loading pipeline
- [`docs/experiments_and_learnings.md`](docs/experiments_and_learnings.md): Evaluation results and benchmarks
