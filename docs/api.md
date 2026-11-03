# API Reference Documentation

Comprehensive specification for all REST endpoints across the **Bank Complaint AI Desk** platform.

All authenticated endpoints require an Authorization header:  
`Authorization: Bearer <access_token>`

---

## 1. Authentication & RBAC (`/auth`)

### `POST /auth/signup`
Registers a new bank agent account. Requires Cloudflare Turnstile bot verification.
- **Rate Limit**: 10 requests / minute
- **Request Body**:
  ```json
  {
    "email": "agent@bank.com",
    "password": "Password123@",
    "confirm_password": "Password123@",
    "full_name": "Jane Doe",
    "turnstile_token": "0.cf-turnstile-token..."
  }
  ```
- **Response**: `201 Created` with initial pending verification status.

### `POST /auth/login`
Authenticates user credentials, validates bot protection, and returns a scoped JWT bearer token.
- **Rate Limit**: 10 requests / minute
- **Request Body**:
  ```json
  {
    "email": "agent@bank.com",
    "password": "Password123@",
    "turnstile_token": "0.cf-turnstile-token..."
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user": {
      "id": 12,
      "email": "agent@bank.com",
      "full_name": "Jane Doe",
      "role": "agent"
    }
  }
  ```

### `POST /auth/google`
Authenticates via Google Identity Services OAuth 2.0 credential.
- **Validates**: Google cryptographic RSA token signature, issuer (`accounts.google.com`), clock-skew tolerance, and `email_verified == true`.
- **Request Body**: `{"credential": "<google_id_token>"}`
- **Response**: `200 OK` with access token and profile.

### `GET /auth/verify-email`
Verifies user email address and activates account.
- **Query Param**: `token` (cryptographic SHA-256 hash verified against database).
- **Response**: `200 OK` with confirmation message.

### `POST /auth/forgot-password`
Issues a time-limited (15 minutes) password reset token delivered via Brevo / SMTP.
- **Rate Limit**: 5 requests / minute
- **Request Body**: `{"email": "agent@bank.com"}`
- **Response**: `200 OK`

### `POST /auth/reset-password`
Resets password using verified token. Increments `token_version` to immediately invalidate all previously issued JWTs.
- **Request Body**:
  ```json
  {
    "token": "reset_token_str",
    "new_password": "NewStrongPassword123@",
    "confirm_password": "NewStrongPassword123@"
  }
  ```
- **Response**: `200 OK`

### `POST /auth/role-upgrade` *(Agent / Supervisor)*
Submits a formal request to elevate user role to Supervisor or Admin.
- **Request Body**: `{"requested_role": "supervisor", "reason": "Promoted to Grievance Lead"}`
- **Response**: `201 Created`

### `GET /auth/role-upgrade/pending` *(Admin only)*
Lists all pending role elevation requests with applicant details and request timestamp.

### `POST /auth/role-upgrade/{request_id}/approve` *(Admin only)*
Approves a promotion request, updates user role in database, and sends confirmation email.

### `POST /auth/role-upgrade/{request_id}/reject` *(Admin only)*
Rejects an elevation request and notifies applicant.

### `GET /auth/users` *(Admin only)*
Returns directory of all system users, active statuses, roles, and assigned supervisors.

### `POST /auth/users/update-role` *(Admin only)*
Direct administrative role override for any user account.
- **Request Body**: `{"user_id": 14, "role": "supervisor"}`

---

## 2. Complaints Intelligence (`/complaints`)

### `GET /complaints`
Paginated search and multi-parameter filtering across millions of records.
- **Performance**: Powered by `pg_trgm` GIN indexes and numeric primary-key optimizations.
- **Query Params**:
  * `page` (int, default 1)
  * `page_size` (int, default 25, max 100)
  * `product` (string)
  * `company` (string)
  * `state` (string, 2-letter uppercase)
  * `date_from` (YYYY-MM-DD)
  * `date_to` (YYYY-MM-DD)
  * `q` (string, searches ID, issue, company, or customer email)
- **Response**: `{"total": 45210, "page": 1, "page_size": 25, "items": [...]}`

### `POST /complaints`
Manually records a customer dispute received via phone, in-branch, or direct mail.
- **Request Body**:
  ```json
  {
    "product": "Checking or savings account",
    "sub_product": "Checking account",
    "issue": "Managing an account",
    "sub_issue": "Fee problem",
    "company": "Chase Bank",
    "state": "NY",
    "consumer_email": "consumer@example.com",
    "narrative": "Unauthorized $35 overdraft fee charged after deposit was cleared.",
    "submitted_via": "Web Portal"
  }
  ```

### `POST /complaints/extract-file`
Universal multi-format parser extracting narrative text, product category, and customer email from uploaded files.
- **Supported Formats**: PDF (`.pdf`), Word (`.docx`), Excel (`.xlsx`, `.xls`), CSV (`.csv`), Text (`.txt`).
- **Form Data**: `file` (multipart/form-data upload, max 25MB).
- **Response**:
  ```json
  {
    "filename": "Dispute_Letter.pdf",
    "extracted_text": "...",
    "detected_product": "Checking or savings account",
    "detected_email": "customer@example.com",
    "is_multi_record": false,
    "record_count": 1
  }
  ```

### `POST /complaints/batch-create`
Batch inserts multiple complaints parsed from an Excel or CSV file.
- **Request Body**: `{"complaints": [...]}`
- **Response**: `{"created_count": 45, "skipped_count": 0}`

### `GET /complaints/{complaint_id}`
Returns complaint metadata, raw narrative, and cached AI root-cause analysis.

### `PUT /complaints/{complaint_id}/email`
Updates or corrects customer email address.
- **Access Control**: Strictly restricted to **Supervisors**, **Admins**, or the assigned complaint owner (preventing unauthorized redirection of resolution letters).
- **Request Body**: `{"consumer_email": "updated_customer@example.com"}`

### `POST /complaints/{complaint_id}/analysis`
Generates zero-shot banking categorization, root-cause classification, urgency scoring, and a 2-sentence executive summary.
- **Caching**: Stored in `complaint_analysis` table for instant retrieval.
- **Query Param**: `refresh` (boolean, bypass cache).

### `GET /complaints/{complaint_id}/similar`
Retrieves top-k historically resolved complaints using `pgvector` HNSW cosine similarity.
- **Query Param**: `top_k` (default 3, max 10).

### `POST /complaints/{complaint_id}/draft-reply`
Drafts a legally grounded bank response letter synthesizing the customer's dispute, similar resolved precedents, and applicable statutory guidelines.
- **Request Body**: `{"custom_instructions": "Offer $50 goodwill credit and waive overdraft fee."}`
- **Response**: `{"complaint_id": 10542, "draft": "Dear Customer..."}`

### `POST /complaints/{complaint_id}/request-approval` *(Agent)*
Submits an agent's drafted letter to the supervisory review queue.
- **Request Body**: `{"response_text": "Drafted letter text..."}`

### `GET /complaints/approvals/pending` *(Supervisor / Admin)*
Lists all drafted responses awaiting review and approval.

### `POST /complaints/{complaint_id}/approve` *(Supervisor / Admin)*
Formally approves the draft response and automatically dispatches the resolution letter via Brevo transactional email.
- **Request Body**: `{"response_text": "Approved letter...", "consumer_email": "customer@example.com"}`
- **Response**: `{"status": "approved", "email_dispatched": true}`

### `POST /complaints/{complaint_id}/reject` *(Supervisor / Admin)*
Rejects a drafted letter with feedback notes returned to the agent for revision.
- **Request Body**: `{"reason": "Please cite Regulation E 10-day provisional credit timeline explicitly."}`

### `POST /complaints/{complaint_id}/dispatch` *(Supervisor / Admin)*
Manually marks an approved complaint response as dispatched if external postal delivery was utilized.

---

## 3. Regulatory Compliance RAG (`/regulations`)

### `POST /regulations/ask`
Hybrid semantic search engine across official Code of Federal Regulations rulebooks (Regulation E - 12 CFR Part 1005, Reg Z, Reg V, Reg F).
- **Hybrid Search**: Combines `pgvector` cosine similarity with lexical section boosts (`§ 1005.11`, `1026.13`).
- **Similarity Threshold**: Rejects out-of-domain questions (`similarity < 0.40`) to prevent hallucinations.
- **Request Body**:
  ```json
  {
    "question": "What is the timeline for provisional credit under Regulation E?",
    "top_k": 4
  }
  ```
- **Response**:
  ```json
  {
    "question": "What is the timeline for provisional credit under Regulation E?",
    "answer": "Under 12 CFR § 1005.11(c), if a financial institution cannot complete its investigation within 10 business days...",
    "citations": [
      {
        "source_id": 1,
        "regulation": "Regulation E (12 CFR Part 1005) - Electronic Fund Transfers",
        "section": "1005.11",
        "page_number": 42,
        "similarity": 0.8842,
        "excerpt": "..."
      }
    ],
    "model": "llama-3.3-70b-versatile"
  }
  ```

---

## 4. Trends & Anomaly Detection (`/trends`) - *Supervisor / Admin*

### `GET /trends/spikes`
Statistical time-series anomaly detection identifying complaint volume surges.
- **Query Params**:
  * `group_by`: `product`, `issue`, or `company` (default: `product`)
  * `window_days`: Rolling analysis window in days (default: 7, max: 180)
  * `baseline_windows`: Number of historical comparison periods (default: 4)
  * `threshold`: Ratio multiplier triggering an anomaly alert (default: 1.5 = 150% volume)
  * `min_count`: Minimum complaint count threshold (default: 10)
  * `date_from` / `date_to`: Custom historical date range analysis
- **Response**: Returns current window count, baseline average, percentage change, and `is_spike: true/false`.

---

## 5. System Health (`/`)

### `GET /health`
Returns system status, active LLM model, and microservice information.
- **Response**: `{"status": "ok", "app": "Bank Complaint AI Desk", "model": "llama-3.3-70b-versatile"}`

### `GET /health/db`
Verifies PostgreSQL connection pool availability. Returns `200 OK` or `503 Service Unavailable`.
