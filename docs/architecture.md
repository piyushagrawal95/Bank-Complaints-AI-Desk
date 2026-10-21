# System Architecture & Design Choices

## High-Level Architecture Overview

The system is designed as an enterprise AI intelligence portal tailored for a bank's dispute and complaint resolution operations.

```
+-----------------------------------------------------------+
|                     React Frontend                        |
|   (Complaints Search, Ask Rules RAG, Trends, Reply Draft) |
+-----------------------------+-----------------------------+
                              | HTTPS / JSON (JWT Auth)
                              v
+-----------------------------------------------------------+
|                 FastAPI Application Layer                 |
|  - Auth & RBAC (Agent, Supervisor, Admin)                 |
|  - Pagination, Filters, Spike Detection Algorithm         |
|  - RAG Orchestrator & Grounding Prompt Engine             |
|  - Caching Layer for AI Categorizations                   |
+---------------+-----------------------------+-------------+
                |                             |
                v                             v
+-----------------------------+ +---------------------------+
|   PostgreSQL + pgvector     | |   Switchable LLM Engine   |
|  - complaints (B-Tree Idx)  | |  - Groq / OpenAI          |
|  - regulation_chunks (HNSW) | |  - Local FastEmbed        |
|  - complaint_embeddings     | |    (bge-small-en-v1.5)    |
|  - complaint_analysis       | +---------------------------+
|  - users & reset_tokens     |
+-----------------------------+
```

---

## Architectural Rationale & Design Choices

### 1. Vector Search: PostgreSQL with `pgvector` vs Standalone Vector DBs
- **Decision**: Used `pgvector` with HNSW indexing directly in PostgreSQL.
- **Why**: Eliminates distributed synchronization issues between relational complaint data and vector indexes. Transactions, backups, and security remain unified in a single database.

### 2. Dual-Layer AI Model Architecture (Local Embeddings + Remote LLM)
- **Decision**: Used local ONNX-based `fastembed` (`bge-small-en-v1.5`, 384 dimensions) for chunk vectorization and Groq/OpenAI for LLM inference.
- **Why**: 
  - Zero embedding cost and no network round-trips for indexing thousands of PDF pages.
  - LLM inference runs via ultra-fast Groq Llama/Qwen models for sub-second agent query turnaround.

### 3. Strict RAG Grounding & Hallucination Mitigation
- **Decision**: Injected official Code of Federal Regulations (CFR) Section headers and page numbers into the prompt context with strict negative constraints ("Answer ONLY using provided text").
- **Why**: In banking compliance, a wrong answer can result in severe federal fines. Verifiable citations allow human agents to cross-check claims immediately.

### 4. Anomaly Spike Detection Algorithm
- **Decision**: Rolling time-series baseline comparison in SQL using dynamic date windowing.
- **Why**: Directly aggregates time buckets in the database using indices rather than pulling millions of rows into Python memory.
