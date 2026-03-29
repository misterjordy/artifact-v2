# Sprint 0: Infrastructure

## Definition of Success
- VPS accessible via SSH
- Docker + Docker Compose installed
- Git repo initialized with project skeleton
- `docker-compose up` starts 4 containers (web, worker, postgres, redis)
- `curl https://artifact.jordanaallred.com/api/v1/health` returns `{"status": "healthy"}`
- HTTPS via Let's Encrypt
- Claude Code connected and can edit/run code on VPS

## Deliverables

### docker-compose.yml
```yaml
services:
  web:
    build: { context: ., dockerfile: docker/Dockerfile }
    command: uvicorn artiFACT.main:app --host 0.0.0.0 --port 8000 --reload
    ports: ["8000:8000"]
    volumes: [".:/app"]
    env_file: .env
    depends_on: [postgres, redis]

  worker:
    build: { context: ., dockerfile: docker/Dockerfile.worker }
    command: celery -A artiFACT.kernel.background worker --loglevel=info
    volumes: [".:/app"]
    env_file: .env
    depends_on: [postgres, redis]

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: artifact_db
      POSTGRES_USER: artifact
      POSTGRES_PASSWORD: artifact_dev
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports: ["9000:9000", "9001:9001"]
    volumes: [miniodata:/data]

volumes:
  pgdata:
  miniodata:
```

### Dockerfile
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
# ZT Pillar 4: Run as non-root (prevent container escape privilege escalation)
RUN useradd -r -s /bin/false -d /app appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "artiFACT.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### pyproject.toml
```toml
[project]
name = "artiFACT"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi==0.115.6",
    "uvicorn[standard]==0.34.0",
    "sqlalchemy[asyncio]==2.0.36",
    "asyncpg==0.30.0",
    "alembic==1.14.1",
    "pydantic==2.10.4",
    "redis[hiredis]==5.2.1",
    "celery[redis]==5.4.0",
    "httpx==0.28.1",
    "python-multipart==0.0.20",
    "jinja2==3.1.5",
    "structlog==24.4.0",
    "cryptography==44.0.0",
    "boto3==1.35.86",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.4",
    "pytest-asyncio==0.24.0",
    "pytest-cov==6.0.0",
    "httpx==0.28.1",
    "ruff==0.8.6",
    "mypy==1.14.1",
    "pip-audit==2.7.3",
    "cyclonedx-bom==4.6.0",
]

[tool.ruff]
line-length = 100

[tool.mypy]
strict = true
```

**NOTE ON PINNING**: Every dependency is pinned to an exact version. To update:
```bash
# Check for vulnerabilities
docker compose exec web pip-audit

# Update one package
# Edit version in pyproject.toml, rebuild:
docker compose up --build
# Run tests to verify nothing broke
docker compose exec web pytest
```

### SBOM Generation (runs in CI, also runnable locally)
```bash
# Generate Software Bill of Materials (EO 14028 requirement)
docker compose exec web cyclonedx-py environment -o sbom.json --format json
# Output: sbom.json (CycloneDX format, machine-readable)

# Audit for known vulnerabilities
docker compose exec web pip-audit --format json -o audit.json
```
Add both to `.gitlab-ci.yml` in the lint stage (Sprint 0 deliverable):
```yaml
sbom:
  stage: lint
  script:
    - cyclonedx-py environment -o sbom.json --format json
    - pip-audit --format json -o audit.json
  artifacts:
    paths: [sbom.json, audit.json]
```

### .env
```
DATABASE_URL=postgresql+asyncpg://artifact:artifact_dev@postgres:5432/artifact_db
REDIS_URL=redis://redis:6379
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=artifact-dev
SECRET_KEY=change-me-in-production
APP_ENV=development
```

### artiFACT/main.py (skeleton)
```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="artiFACT", version="0.1.0")

@app.get("/api/v1/health")
async def health():
    # Sprint 0: just prove the stack runs
    return {"status": "healthy"}
```

### Directory structure to create
```
artiFACT/
├── __init__.py
├── main.py
├── kernel/
│   └── __init__.py
├── modules/
│   └── __init__.py
├── static/
├── templates/
docker/
├── Dockerfile
├── Dockerfile.worker
migrations/
├── env.py
├── versions/
tests/
├── __init__.py
├── conftest.py
.env
.gitignore
docker-compose.yml
pyproject.toml
alembic.ini
README.md
```

## Verification Commands
```bash
docker compose up --build -d
curl http://localhost:8000/api/v1/health
# Should return: {"status":"healthy"}

# Then after nginx + certbot:
curl https://artifact.jordanaallred.com/api/v1/health
```
