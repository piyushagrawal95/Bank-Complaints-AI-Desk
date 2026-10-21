# API Reference Documentation

All endpoints (except `/health`, `/auth/signup`, `/auth/login`, and `/auth/forgot-password`) require a JWT Bearer token in the `Authorization: Bearer <token>` header.

---

## 1. Authentication (`/auth`)

### `POST /auth/signup`
Creates a new bank agent account.
- **Request Body**: `{"email": "agent@bank.com", "password": "secure_password", "full_name": "John Doe"}`
- **Response**: `201 Created` with user details.

### `POST /auth/login`
Authenticates a user and issues a JWT token.
- **Request Body**: `{"email": "agent@bank.com", "password": "secure_password"}`
- **Response**: `200 OK` with `access_token`, `token_type`, and user profile.

### `POST /auth/forgot-password`
Generates a secure 15-minute reset token.
- **Request Body**: `{"email": "agent@bank.com"}`
- **Response**: `200 OK`

### `POST /auth/reset-password`
Resets password using valid token.
- **Request Body**: `{"token": "reset_token_str", "new_password": "new_secure_password"}`

---

## 2. Complaints Intelligence (`/complaints`)

### `GET /complaints`
Paginated search and multi-filter query.
- **Query Params**: `page` (default 1), `page_size` (default 25), `product`, `company`, `state`, `date_from`, `date_to`, `q` (text search).

### `GET /complaints/{complaint_id}`
Returns full complaint details and cached AI analysis.

### `POST /complaints/{complaint_id}/analysis`
Classifies complaint and generates 2-sentence summary using LLM.
- **Query Param**: `refresh` (boolean, bypass cache).

### `GET /complaints/{complaint_id}/similar`
Returns top-k similar complaints using pgvector semantic search.

### `POST /complaints/{complaint_id}/draft-reply`
Drafts a formal bank response letter using similar resolved cases and regulatory rules.

---

## 3. Regulation RAG (`/regulations`)

### `POST /regulations/ask`
Answers compliance questions using pgvector cosine similarity + grounded LLM synthesis.
- **Request Body**: `{"question": "How many days does a bank have to resolve an electronic error?", "top_k": 4}`
- **Response**: Answer text with array of `citations` containing CFR Section, PDF Page, Similarity Score, and Excerpt.

---

## 4. Trends & Alerts (`/trends`) - *Supervisor / Admin only*

### `GET /trends/spikes`
Calculates operational complaint spikes comparing recent window vs historical baseline.
- **Query Params**: `group_by` (product, issue, company), `window_days` (default 7), `threshold` (default 1.5x), `min_count` (default 30).
