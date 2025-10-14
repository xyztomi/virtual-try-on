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
