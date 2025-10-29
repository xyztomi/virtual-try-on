## Virtual Try-On Project

### Development Setup

#### 1. Clone the repository
```bash
git clone https://github.com/xyztomi/virtual-try-on
cd virtual-try-on
```

#### 2. Install dependencies (Backend)
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Start backend development server
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Deployment (Docker)

> Prerequisites: Docker (24+) and Docker Compose (v2, typically included with Docker Desktop).

1. **Populate environment variables**
	```bash
	cp .env.example .env
	# Edit .env with your keys (Gemini, Supabase, Turnstile, etc.)
	```

2. **Build the production image**
	```bash
	docker build -t virtual-try-on-api:latest .
	```

3. **Run the container**
	```bash
	docker run -d \
	  --name virtual-try-on-api \
	  --env-file .env \
	  -p 8000:8000 \
	  virtual-try-on-api:latest
	```

	The service is now available at `http://localhost:8000/api/v1/health`.

4. **(Optional) Use Docker Compose**
	```bash
	docker compose up --build
	```

	Compose automatically loads `.env`, applies resource limits, and keeps the container running with restart policies.

#### Runtime configuration

The container exposes the following environment variables to tweak behaviour:

| Variable | Default | Description |
|----------|---------|-------------|
| `UVICORN_HOST` | `0.0.0.0` | Bind address inside the container |
| `UVICORN_PORT` | `8000` | Port exposed by the ASGI server |
| `UVICORN_WORKERS` | `2` | Number of Uvicorn worker processes |
| `UVICORN_LOG_LEVEL` | `info` | Log level for request handling |

**Note:** supply production secrets via `docker run -e KEY=value` or an orchestrator secret store rather than baking them into the image.

### API Endpoints

#### Try-On Endpoints
- `POST /api/v1/tryon` – Create a virtual try-on job
  - Requires: Turnstile token in `X-Turnstile-Token` header
  - Body: Multipart form with `body_image`, `garment_image1`, optional `garment_image2`
  - Returns: `record_id` and `result_url`

- `GET /api/v1/tryon/{record_id}` – Fetch job status/result

- `POST /api/v1/tryon/audit` – Audit a try-on result quality
  - Requires: Turnstile token in `X-Turnstile-Token` header
  - Body: JSON with `model_before`, `model_after`, `garment1`, optional `garment2` (URLs or base64)
  - Returns: Quality score, issues list, and validation flags
  - **Use this separately after try-on to check quality and track audit history**

#### Authentication Endpoints
- `POST /api/v1/auth/register` – Register new user account
- `POST /api/v1/auth/login` – Login with email/password
- `POST /api/v1/auth/logout` – Invalidate session token
- `GET /api/v1/auth/me` – Get current user profile
- `GET /api/v1/auth/history` – Get user's try-on history (with pagination)
- `GET /api/v1/auth/history/{record_id}` – Get specific history record
- `DELETE /api/v1/auth/history/{record_id}` – Delete a history record
- `GET /api/v1/auth/stats` – Get user statistics (total, success rate, etc.)

#### Utility Endpoints
- `GET /api/v1/ratelimit` – Check current rate limit status
- `GET /api/v1/health` – Health check

---


### Git Workflow & Branching

1. **Branches:**
	 - `main`: production-ready.
	 - `frontend`: All frontend work happens here.
	 - `backend`: All backend work happens here.

2. **How to create and update your branch:**
	 - Create your branch (if not exists):
		 ```bash
		 git checkout -b frontend   # or backend
		 git push -u origin frontend  # or backend
		 ```
	 - Switch to your branch:
		 ```bash
		 git checkout frontend   # or backend
		 ```
	 - Pull latest changes from main into your branch:
		 ```bash
		 git checkout main
		 git pull origin main
		 git checkout frontend   # or backend
		 git merge main
		 ```

3. **Merging to main:**
	 - Only the project owner (xyztomi) should merge to `main`.
	 - When your work is ready, push your branch and open a pull request (PR) to `main`.
	 - The owner reviews and merges the PR.

4. **Commit often:** Use clear, concise commit messages.

---

---
