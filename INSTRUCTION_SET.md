# Project Overview and Architecture

The Bank Complaint AI Desk is an enterprise-grade banking dispute platform designed to streamline grievance resolution and statutory compliance.
Key capabilities include:

1. Universal Complaint Ingestion : 
Ingests massive CFPB dispute datasets alongside user-uploaded dispute documents (PDF,Word, Excel,CSV.TXT) with automatic field extraction

2. AI-Powered Root-Cause and Summarization :
Employs Large Language Model (LLMs) to classify root causes, evaluate complaint urgency and produce high impact 2 sentence executive summaries

3. "Ask the Rules" RAG Engine :
Performs semantic similarity searches (pgvector) over federal banking regulations to deliver answers backed by exact CFR section and PDF page citations.

4. Context Aware Precedent Retrieval and Draft Generation :
Identifies historical resolved complaints with high vector similarity to draft legally complaint customer response letters

5. Role Based Approval & Automated Email Dispatch :
Implements an operational workflow where Agents submit drafts and Supervisors/ Admins review, approve and automatically dispatch resolution letter via email

---

## 2. Role-Based Access Control (RBAC) & Account Setup

The platform enforces three strict operational access levels:

| Role | User Persona | Operational Permissions |
| :--- | :--- | :--- |
| **Agent** | Frontline Dispute Analyst | Search & filter complaints, ingest dispute files, run AI summarization, generate response drafts, and submit drafts for approval. |
| **Supervisor** | Compliance & Team Lead | All Agent capabilities, plus access to the **Approvals Portal** to review/approve drafts, trigger automated resolution emails to consumers, and analyze **Trends & Volume Spikes**. |
| **Admin** | Systems & Compliance Director | All Supervisor capabilities, plus full access to **User Management** to approve role upgrades and configure system parameters. |

### Authentication Procedure:
1. Navigate to the live web portal: **https://bank-complaints-ai-desk.vercel.app**.
2. Click "Sign In / Get Started" on the top navigation bar.
3. To create a test account:
   - Click "Create an account".
   - Enter your email address and a strong password (minimum 8 characters with uppercase, lowercase, number, and symbol).
   - Solve the verification math CAPTCHA and submit.
4. **Role Upgrades**: New signups receive the **Agent** role by default. To elevate an account to **Supervisor** or **Admin**:
   - Click the User Profile badge in the top-right corner.
   - Click **"Request Role Upgrade"** select the desired role, and submit.
   - The Super Admin (`piyushagrawal300504@gmail.com`) can approve the request from the **User Management** tab.


