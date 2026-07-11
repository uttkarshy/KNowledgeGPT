# Running KnowledgeGPT locally

## Prerequisites
- Docker + Docker Compose v2
- An OpenAI API key
- (Optional) AWS credentials with S3 access, or see the MinIO note below for a fully local setup

## Quick start

```bash
cp .env.example .env
# edit .env: at minimum set OPENAI_API_KEY and JWT_SECRET_KEY

make up
```

This starts, in order of dependency:
1. **postgres** (`pgvector/pgvector:pg16`) — the database, with the pgvector extension pre-installed
2. **redis** — Celery broker/result backend + rate-limit counters
3. **clamav** — virus scanning daemon. **Takes several minutes on first boot** to download virus definitions; the backend's virus-scan step retries rather than failing hard while this warms up.
4. **backend** — the FastAPI API. Runs Alembic migrations automatically on startup (`RUN_MIGRATIONS=true`), then serves on `http://localhost:8000`.
5. **celery-worker** — same image as `backend`, different command; processes document uploads (extraction, OCR, chunking, embedding).
6. **frontend** — the Next.js app, `http://localhost:3000`.

Once everything is healthy:
- API docs: http://localhost:8000/docs
- App: http://localhost:3000

## Running without real AWS (MinIO)

The upload pipeline talks to S3 via presigned URLs. To develop fully locally
without an AWS account, run a MinIO container and point `AWS_S3_ENDPOINT_URL`
at it (see `app/core/config.py` — this field exists specifically for this):

```yaml
# add to docker-compose.yml
minio:
  image: minio/minio
  command: server /data --console-address ":9001"
  ports: ["9000:9000", "9001:9001"]
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin
```

Then set in `.env`: `AWS_S3_ENDPOINT_URL=http://minio:9000`, and create the
bucket once via the MinIO console at `http://localhost:9001`.

## Common commands

| Command | What it does |
|---|---|
| `make up` | Start everything, rebuilding images |
| `make down` | Stop everything, keep data |
| `make clean` | Stop everything, **delete all data** |
| `make logs` | Tail all service logs |
| `make migrate` | Run migrations manually |
| `make migration name="add x"` | Generate a new Alembic migration |
| `make shell-backend` | Shell into the API container |
| `make shell-db` | psql shell into the dev database |

## What's verified vs. not

Everything in this repo was built and unit/integration-tested against real
generated files, a real running Tesseract OCR install, and mocked
DB/provider layers (see the increment-by-increment notes in the project
history) — but this `docker-compose.yml` itself, and the containers it
builds, have **not** been run end-to-end, because this project was built in
a sandboxed environment without a Docker daemon available. Before relying on
this, run `make up` yourself and work through:
1. Register a user, verify the email link logs correctly (or arrives, if
   you configure real SMTP)
2. Create a knowledge base, upload a real PDF, watch it move through
   `pending -> virus_scanning -> extracting -> chunking -> embedding -> completed`
3. Ask it a question and confirm you get a cited, streamed answer
