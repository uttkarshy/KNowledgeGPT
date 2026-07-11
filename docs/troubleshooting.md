# Troubleshooting

## "ClamAV connection refused" / uploads stuck at "Scanning"

ClamAV takes several minutes on first container start to download its
virus definition database before it will accept connections. Check its
logs: `docker compose logs clamav` (or the ECS task logs in production).
The upload pipeline retries with backoff rather than failing hard during
this window — if it's been more than ~10 minutes, something else is
wrong (check connectivity between the worker and ClamAV containers, and
`CLAMAV_HOST`/`CLAMAV_PORT`).

## Uploads stuck at "pending" and never progress

The Celery worker isn't running, or can't reach Redis. Check
`docker compose logs celery-worker`. In production, check the worker
ECS service's task count and CloudWatch logs.

## "I couldn't find that information" for something you know you uploaded

1. Confirm the document's status is actually `completed`, not still
   processing or `failed` — check the Documents panel.
2. The similarity threshold (`RAG_MIN_SIMILARITY`, default 0.72) may be
   filtering out a genuinely relevant but loosely-worded match. This is a
   deliberate tradeoff (favoring "admit I don't know" over answering from
   weak evidence) — lower it in `app/core/config.py` if you'd rather trade
   precision for recall.
3. Check you're asking within the right knowledge base — retrieval is
   scoped per knowledge base by design.

## Hindi (or mixed English/Hindi) OCR isn't recognizing text well

This path was implemented and the language pack (`tesseract-ocr-hin`)
installs and loads correctly, but could not be verified end-to-end with a
real Devanagari-script test image in the sandbox this was built in (no
such font was available there). If results are poor: confirm
`tesseract --list-langs` shows `hin` in your actual deployment, and check
the source image's resolution/contrast — Tesseract's accuracy is
sensitive to scan quality regardless of language.

## Frontend can't reach the backend (CORS errors in the browser console)

Check `CORS_ALLOWED_ORIGINS` in the backend's environment actually
includes your frontend's real origin (including scheme and port). This is
a JSON-array-shaped env var — `'["http://localhost:3000"]'`, not a bare
string.

## `next lint` hangs / CI job never completes

Should not happen — `.eslintrc.json` is committed specifically so `next
lint` runs non-interactively. If you've deleted or renamed it, `next
lint` will prompt interactively for a config choice and hang forever in a
non-interactive CI shell.

## `passlib`/`bcrypt` error: "password cannot be longer than 72 bytes" on an obviously-short password

A known `passlib` 1.7.4 / `bcrypt` >=4.1 incompatibility (passlib
misreads bcrypt's new version string). `requirements.txt` pins
`bcrypt>=4.0.1,<4.1` specifically to avoid this — if you've bumped it
past that pin, this is why.

## Terraform: `terraform apply` fails immediately, or ECS services never reach steady state

Almost always one of:
- No image pushed yet to one of the two ECR repos (see the deployment
  guide's step 3 — Terraform creates the repos empty, you push the first
  image manually or via the `deploy` workflow).
- `db_master_password` / `jwt_secret_key` weren't set via `TF_VAR_*`
  environment variables before `apply` — these have no default and
  Terraform will prompt for them interactively if missing, which usually
  looks like a hang in CI.
- Security group rules genuinely correct but a task's `health_check` path
  is wrong for a customized image — check `/health` really is what your
  running container serves.
