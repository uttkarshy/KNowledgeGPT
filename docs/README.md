# KnowledgeGPT Documentation

| Document | What's in it |
|---|---|
| [architecture.md](architecture.md) | System diagram, request-time paths, provider abstraction pattern, directory layout, key design decisions |
| [database-schema.md](database-schema.md) | Every table/column/FK, generated directly from the live SQLAlchemy models |
| [api-reference.md](api-reference.md) | Every route, generated directly from the live OpenAPI schema (`openapi.json` in this directory) |
| [deployment-guide.md](deployment-guide.md) | Local Docker setup, AWS production deployment, migration policy, pre-deployment checklist |
| [developer-guide.md](developer-guide.md) | Running tests, adding a new LLM provider or file-format extractor, migrations, code organization rules |
| [user-guide.md](user-guide.md) | End-user walkthrough: knowledge bases, uploading, chatting, admin |
| [troubleshooting.md](troubleshooting.md) | Common issues and how to diagnose them |

Also see the root [`README.md`](../README.md) (local dev quick-start) and
[`infra/README.md`](../infra/README.md) (Terraform/AWS one-time setup).

## A note on how this was built and what's actually verified

This project was built incrementally in a sandboxed environment without
Docker, AWS credentials, or a live Postgres/OpenAI/ClamAV instance
available. Wherever that mattered, each piece was verified in the most
real way available:

- The database schema and API reference above are **generated from the
  live code**, not hand-written — they can't drift from reality the way
  prose documentation can.
- Extraction, OCR, chunking, and the RAG engine's core safety property
  (never answering outside retrieved context) were tested against real
  generated files and real running Tesseract OCR — see
  `backend/tests/` and the increment-by-increment build notes for exactly
  what was run and what it proved.
- Infrastructure (Terraform, Docker) was validated as thoroughly as
  possible without live cloud access: real HCL parsing and cross-module
  reference checks for Terraform, an actual `next build` and a real
  standalone Next.js server run for the frontend Docker image.

What was **not** verified, and should be your first checkpoints before
trusting this in production: an actual `docker compose up`, an actual
`terraform apply` against real AWS, and a live end-to-end pass with a
real OpenAI API key and real ClamAV virus definitions. The
[deployment-guide.md](deployment-guide.md) checklist spells out exactly
what to click through.
