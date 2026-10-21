# Setup and Installation Guide

This document explains how to set up and run the Bank Complaint AI system from scratch on a new developer laptop.

## Prerequisites
- **Python**: 3.10, 3.11, or 3.12
- **Node.js**: 18+ and npm
- **PostgreSQL**: 15+ with the `pgvector` extension installed
- **API Keys**: Groq API Key or OpenAI API Key

---

## 1. Backend Setup

1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   Copy `.env.example` to `.env` and fill in your credentials:
   ```env
   DATABASE_URL=postgresql://postgres:password@localhost:5432/complaints
   JWT_SECRET=generate_a_secure_random_string_here
   FRONTEND_ORIGIN=http://localhost:5173
   LLM_PROVIDER=groq
   LLM_MODEL=qwen/qwen3.8-27b
   GROQ_API_KEY=gsk_your_groq_key
   ```

---

## 2. Database Initialization

From the project root folder (with virtual environment active):

1. **Create tables and vector extensions:**
   ```bash
   python scripts/create_tables.py
   ```

2. **Ingest CFPB complaints dataset:**
   ```bash
   python scripts/load_complaints.py
   ```

3. **Ingest Banking Regulations (Regulation E) with pgvector:**
   ```bash
   python scripts/ingest_regulations.py
   ```

4. **Index Complaint Narratives for Similarity Search:**
   ```bash
   python scripts/embed_complaints.py
   ```

---

## 3. Run Backend Server

```bash
cd backend
uvicorn app.main:app --reload
```
The FastAPI server will be available at: `http://127.0.0.1:8000`  
Interactive Swagger API documentation: `http://127.0.0.1:8000/docs`

---

## 4. Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
2. Open your browser at `http://localhost:5173`.
3. Sign up with a new agent account or log in.
