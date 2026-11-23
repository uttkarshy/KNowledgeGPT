# KnowledgeGPT source audit

23 November 2026 · UtkarshLabs

## Source and deployment

The Android branch starts at GitHub main `2895a01e24137b9ed08f742c3b5b3dbb538e6033`. Main has a Next.js App Router / React / TypeScript website, FastAPI with async SQLAlchemy, PostgreSQL and pgvector, Redis, Celery, temporary S3 storage and an OpenAI Responses provider. The monorepo also contains Docker Compose, Alembic, a Next.js API rewrite, GitHub Actions and Terraform for AWS networking, ALB, ECS, ECR, RDS, cache, storage and secrets. Production configuration and user data were left untouched.

The same repository’s `codex/knowledgegpt-launch-recovery` branch at `7866afe12bff572e9ec46338137209ffc5f2e945` contains the newer product: Gemini embeddings and generation, optional server-side OpenAI chat fallback, OCR/table extraction changes, a processing estimate, credit ledger, resumable processing and a redesigned website. Neither the public site nor its response headers established the exact deployed revision. The Android client uses contracts shared by the two branches and reads capabilities for the differences. Review the newer service and migrations before any deployment of backend changes from this main-based branch.

## Service observations

| Area | Verified in source or local test | Production evidence and open questions |
|---|---|---|
| Account | Register, login, profile, password reset, email verification, bearer auth, rotated opaque refresh tokens and logout. Local two-account flow passed, including session renewal, rejection of a logged-out refresh token and chat recovery after signing back in. | Login, forgot/reset and verify pages returned 200. Unauthenticated profile returned 401. Mail delivery, sign-in for Google-only accounts and recovery-link expiry require a configured staging environment. Android provides email/password access. |
| Knowledge bases | Create/list/get/edit, archive, duplicate, stats and deletion. Android implements create, browse and select. A base owns documents and conversations. | Unauthenticated list returned 401. The feature branch checks folder ownership at creation; the prior main implementation accepted a parent ID without an owner check. |
| Documents | The API signs a single object PUT. Confirm checks the object and queues a worker. The worker validates, scans when enabled, extracts text, chunks it, embeds it, writes pgvector rows and updates status. The synthetic PDF integration exercised indexing, status, deletion and access checks. | Document-list and limits responded 401. Recovery advertises extension/size limits, an estimate and retry states. Credit charging, production storage permissions and error recovery have not been tested against a real account. |
| Chat | Owner-scoped sessions and message queries, filtered pgvector retrieval, persisted passages and citation records, SSE deltas and terminal events. The test generated a real PDF, retrieved its page and reopened the saved answer. Provider output and embeddings in this test were deterministic fixtures. | Unauthenticated sessions returned 401. Real Gemini quality, latency, fallback and device-to-production streaming remain open. No server cancellation endpoint found. |
| Schema | Main migration 0001 creates users, refresh tokens, knowledge bases, documents, chunks, sessions, messages, citations and usage/audit logs. Recovery runs through 0007 with embedding contract checks, token versions, progress/provenance, citation order and credits. | Production Alembic head and live provider config were not read. The branch smoke test migrated an empty disposable PostgreSQL database. |
| Public routing | Root and login returned 200. Protected routes returned JSON. The API origin is the production website. | Both /openapi.json and /api/openapi.json returned 404. /health returned 404 at the public origin. /privacy, /terms and /delete-account returned 404. Public gateway behavior differs from the Terraform route examples. |
| Operator support | Main has admin-only user deletion. This branch adds support, AI-report and account deletion request intake, plus public policy and deletion pages. Receipts require SMTP acceptance. | Production deployment, a monitored support mailbox, reviewer credentials, retention terms and a completed erasure rehearsal are still required. |

## Corrections on the feature branch

- Matched ORM enum storage to the lower-case strings in the migration. This affects document status/type, message role and audit action on main.
- Confirm validates the actual object size and serializes conflicting confirmation requests. It commits the ready-to-queue record before publishing work. A queue failure records a visible failure. Main’s worker now keeps its async DB work on one event loop per invocation and selects a private temporary filename.
- Refresh rotation locks the token row and persists replay revocation. Support checks answer ownership, sends a minimal identifier and reason, and returns a delivery error if the inbox is unavailable. Removed logging of email bodies that contain action tokens.
- Declared SQLAlchemy’s async dependency explicitly. Replaced python-jose with PyJWT for the existing access-token format. The revised Python requirements passed a fresh pip-audit scan.
- The original migration now uses PostgreSQL’s built-in UUID generator when available and requests pgcrypto only on older installations. No migration was applied to an existing user database.

The [API compatibility report](docs/mobile/API_COMPATIBILITY.md) enumerates the routes and schema differences. See [security findings](docs/mobile/SECURITY.md), [test evidence](docs/mobile/testing.md) and the [Android build guide](docs/mobile/BUILD.md).
