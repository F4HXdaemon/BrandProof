# BrandProof — Production Deployment Guide
**Target Architecture: GitHub + Render (FastAPI & PostgreSQL) + Vercel (Next.js)**

This guide provides step-by-step instructions for deploying BrandProof to production environments using:
- **GitHub**: Source code repository
- **Render**: Managed PostgreSQL Database and FastAPI Backend Web Service
- **Vercel**: Next.js 14 Production Frontend

---

## 📋 Pre-Deployment Architecture Overview

```
[ Client Browser ]
       │
       ├─────────────────────────────────┐
       ▼ (HTTPS)                         ▼ (HTTPS / CORS)
[ Vercel Frontend ]              [ Render Backend ]
(Next.js 14 App Router)          (FastAPI + Uvicorn)
       │                                 │
       │                                 ├──────────► [ Render PostgreSQL ]
       │                                 │            (Schema managed via Alembic)
       │                                 │
       └─────────────────────────────────┴──────────► [ S3 / MinIO / R2 ]
                                                      (Document & Version Storage)
```

---

## Step 1: GitHub Repository Setup

1. **Initialize Git Repository** (if not already done):
   ```bash
   git init
   git branch -M main
   ```

2. **Verify Secrets & Exclusions**:
   - Ensure `.gitignore` is active.
   - Verify that no `.env`, `.env.local`, `.env.production`, or `*.db` files are staged.
   - Check status:
     ```bash
     git status
     ```

3. **Add and Commit Clean Source Files**:
   ```bash
   git add .
   git commit -m "feat: production readiness, security hardening, and deployment configuration"
   ```

4. **Push to Private GitHub Repository**:
   - Create a new **Private** repository on GitHub (e.g. `brandproof`).
   - Add remote and push:
     ```bash
     git remote add origin https://github.com/YOUR_GITHUB_USERNAME/brandproof.git
     git push -u origin main
     ```

---

## Step 2: Render Database & Backend Deployment

Render hosts both the PostgreSQL database and the FastAPI web service.

### Option A: 1-Click Blueprint (Recommended)
BrandProof includes a pre-configured `render.yaml` Blueprint at the repository root.

1. Log into your [Render Dashboard](https://dashboard.render.com).
2. Click **New** → **Blueprint**.
3. Connect your GitHub repository `brandproof`.
4. Render automatically detects `render.yaml` and sets up:
   - `brandproof-db` (PostgreSQL standard managed database)
   - `brandproof-backend` (Web Service running Python 3.11 with `preDeployCommand: "alembic upgrade head"`)
   - Persistent disk for local document storage (or S3-compatible cloud storage)
   > 💡 **Concurrent Migration Safety**: Alembic migrations execute via Render's `preDeployCommand`. This runs once in an isolated container prior to routing traffic to new application instances, guaranteeing schema integrity and preventing concurrent migration race conditions during scale-out.
5. Review the plan and click **Apply**.

---

### Option B: Manual Setup on Render

#### 1. Create Render PostgreSQL Database
1. Go to **Dashboard** → **New** → **PostgreSQL**.
2. Name: `brandproof-db`
3. Database: `brandproof`
4. User: `brandproof`
5. Region: Choose your preferred region (e.g., Oregon or Frankfurt).
6. Click **Create Database**.
7. Once provisioned, copy the **Internal Database URL** (for services inside Render) and **External Database URL** (for remote management).

#### 2. Create Render Backend Web Service
1. Go to **Dashboard** → **New** → **Web Service**.
2. Connect your `brandproof` GitHub repository.
3. Configure the service settings:
   - **Name**: `brandproof-backend`
   - **Region**: Same region as your database
   - **Root Directory**: `backend`
   - **Runtime**: `Python`
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/v1/health`

4. Configure **Environment Variables** in Render:
   | Key | Example Value | Description |
   | :--- | :--- | :--- |
   | `PYTHON_VERSION` | `3.11.9` | Python runtime version |
   | `ENVIRONMENT` | `production` | Enables strict security validators |
   | `DEBUG` | `false` | Disables debug mode in production |
   | `PROJECT_NAME` | `BrandProof Brand Governance Platform` | Display name of the platform |
   | `DATABASE_URL` | `postgresql://...` | Connection string from Render PostgreSQL |
   | `SECRET_KEY` | *(Generate 32+ char secret)* | Secure token signing key (`openssl rand -hex 32`) |
   | `ALGORITHM` | `HS256` | JWT signing algorithm |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token validity (24 hours) |
   | `STORAGE_BACKEND` | `local` or `s3` | Object storage mode |
   | `STORAGE_DIR` | `/var/data/storage` | Local storage directory (if using disk) |
   | `CORS_ORIGINS` | `https://your-brandproof.vercel.app` | Vercel frontend URL(s), comma-separated |
   | `ENABLE_DEMO_RESET` | `false` | Must be `false` in production |
   | `ENABLE_DEMO_MODE` | `false` | Set `false` for standard production |

5. *(Optional)* If using S3 object storage (AWS S3, Cloudflare R2, MinIO):
   | Key | Description |
   | :--- | :--- |
   | `STORAGE_BACKEND` | `s3` |
   | `S3_ENDPOINT_URL` | Custom endpoint (e.g. `https://<account_id>.r2.cloudflarestorage.com`) or empty for AWS |
   | `S3_BUCKET_NAME` | S3 bucket name |
   | `S3_ACCESS_KEY` | S3 API Access Key ID |
   | `S3_SECRET_KEY` | S3 API Secret Access Key |
   | `S3_REGION` | AWS / S3 region (e.g. `us-east-1` or `auto`) |

6. Click **Create Web Service**.
7. Once deployed, note your backend URL:
   `https://brandproof-backend.onrender.com`

---

## Step 3: Vercel Frontend Deployment

1. Log into your [Vercel Dashboard](https://vercel.com).
2. Click **Add New** → **Project**.
3. Import your GitHub repository `brandproof`.
4. Configure the Project:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: Click *Edit* and select `frontend`
   - **Build Command**: `npm run build`
   - **Install Command**: `npm ci`
   - **Output Directory**: `.next` (default)

5. Configure **Environment Variables**:
   | Key | Value | Description |
   | :--- | :--- | :--- |
   | `NEXT_PUBLIC_API_URL` | `https://brandproof-backend.onrender.com/api/v1` | Your deployed Render backend API base URL |
   | `NEXT_PUBLIC_ENABLE_DEMO_MODE` | `false` | Set `true` only if you want demo switcher in UI |

6. Click **Deploy**.
7. Once deployed, note your production frontend URL (e.g. `https://brandproof.vercel.app`).

---

## Step 4: Finalize CORS Configuration

After obtaining your Vercel production URL:
1. Return to the **Render Dashboard** → `brandproof-backend` → **Environment**.
2. Update `CORS_ORIGINS` to include your Vercel URL:
   ```
   https://brandproof.vercel.app,https://brandproof-staging.vercel.app
   ```
3. Save changes. Render will automatically redeploy the backend service.

---

## 🔒 Security Architecture & Token Threat Model

BrandProof employs a hardened defense-in-depth security model:

### 1. Bearer Token Architecture & Mitigations
Authentication uses cryptographically signed JWT access tokens passed via the `Authorization: Bearer <token>` HTTP header.
- **Query Parameter Tokens Disabled**: Access tokens in URL query strings (`?token=`) are strictly prohibited and rejected across all API endpoints, including file downloads and export routes. This prevents access token leakage in browser history, proxy logs, and HTTP Referer headers.
- **XSS & Storage Threat Analysis**: Storing JWTs in browser `localStorage` carries the inherent risk that an XSS vulnerability could allow malicious scripts to read tokens. To thoroughly mitigate this:
  - **Content Security Policy (CSP)**: Configured in `frontend/next.config.mjs` with `default-src 'self'`, `frame-ancestors 'none'`, and restricted external sources to prevent script injection.
  - **Sanitized Errors**: The FastAPI backend strips raw submitted values from validation error responses, ensuring credentials and tokens are never echoed in logs or responses.
  - **Short Expiration & Cryptographic Signing**: JWTs expire after `ACCESS_TOKEN_EXPIRE_MINUTES` and are signed using HS256 with an independently provisioned 256-bit secret.
  - **Strict CORS & Origin Verification**: Backend enforces `CORS_ORIGINS` to allow requests only from verified frontend origins with full credential checking.

### 2. Demo Environment Isolation
- `ENABLE_DEMO_RESET` is strictly `false` by default and forced to `false` in production.
- Demo passwords are never hardcoded. In staging/development, demo accounts can be provisioned using the `DEMO_USER_PASSWORD` environment variable.
- Automated seeding is prohibited in production.

---

## Step 5: Post-Deployment Verification Checklist

Execute these verifications on your live production URLs:

- [ ] **Health Endpoint**: Open `https://YOUR-BACKEND.onrender.com/api/v1/health`. Returns `{"status":"healthy","database":"healthy"}`.
- [ ] **Root Endpoint**: Open `https://YOUR-BACKEND.onrender.com/`. Returns `{"status":"operational"}`.
- [ ] **Frontend Load**: Open `https://YOUR-FRONTEND.vercel.app/`. Landing page loads cleanly over HTTPS.
- [ ] **Organization Registration**:
  - Visit `/login` or register a new account.
  - Verify that providing an existing organization slug does NOT allow takeover (returns 409 Conflict).
  - Verify that a newly registered organization is completely isolated.
- [ ] **Login & Authentication**: Sign in and verify access token issuance.
- [ ] **Dashboard Loading**: Verify KPIs and live data render without errors.
- [ ] **Document Ingestion**: Upload a sample draft (.txt, .md, .docx, or .pdf) and verify chunking & claim extraction.
- [ ] **Governance Pipeline**: Verify rule checkers, findings, and CitationGate ("NO VALID SOURCE = NO FINDING").
- [ ] **Cardinal Blocker Policy**: Verify that drafts with open Blocker findings cannot be approved without executive override.
- [ ] **Audit Trail**: Visit `/audit` and confirm audit events are immutably logged.
- [ ] **Database Persistence**: Restart the backend service on Render and verify that all registered users and documents remain intact.

---

## 🛠️ Troubleshooting & Support

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **CORS error in browser console** | `CORS_ORIGINS` on Render does not match Vercel URL | Add exact Vercel origin (including `https://`, no trailing slash) to `CORS_ORIGINS` on Render. |
| **Backend 503 on `/health`** | PostgreSQL database unreachable | Check `DATABASE_URL` in Render service environment settings. |
| **Migrations failed on deploy** | Incompatible schema or connection timeout | Check Render build logs for `alembic upgrade head`. Ensure PostgreSQL database is online. |
| **Document upload returns 500** | S3 credentials missing or storage volume unwritable | Check `STORAGE_BACKEND`. If `s3`, ensure valid `S3_ACCESS_KEY` & `S3_SECRET_KEY`. If `local`, ensure persistent disk is mounted. |
