> Current local setup and acceptance commands: [local-validation.md](local-validation.md).
> Production deployment is paused; do not run Terraform for this milestone.

# Deployment Guide

## Local (Docker Compose)

See the root [`README.md`](../README.md) for the full quick-start. Summary:

```bash
cp .env.example .env    # fill in OPENAI_API_KEY and JWT_SECRET_KEY at minimum
make up
```

API: http://localhost:8000/docs · App: http://localhost:3000

## Production (AWS via Terraform)

See [`infra/README.md`](../infra/README.md) for the full one-time setup
(remote state, ACM certificate, secrets, GitHub OIDC role) and apply steps.
Summary of the path from zero to a running deployment:

1. One-time: create the Terraform state S3 bucket + DynamoDB lock table by hand.
2. `terraform apply` in `infra/terraform/environments/production` — this
   creates the VPC, RDS, ElastiCache, S3, ECR, ALB, and ECS
   cluster/services/task definitions.
3. Push the first backend and frontend images to the ECR repos Terraform
   just created (the ECS services can't start until at least one image
   exists).
4. Configure the GitHub repo's `AWS_DEPLOY_ROLE_ARN` and
   `PUBLIC_API_BASE_URL` (Settings, Secrets and variables, Actions,
   Variables) using Terraform's `deploy_role_arn` output and the ALB's
   DNS name.
5. From then on, every push to `main` runs `.github/workflows/deploy.yml`:
   build both images tagged with the commit SHA, push to ECR, register a
   new task definition revision per service, update the ECS services, and
   wait for them to stabilize.

## Database migrations in production

The backend container's entrypoint (`backend/entrypoint.sh`) runs
`alembic upgrade head` automatically on startup, gated by
`RUN_MIGRATIONS=true` (set only on the API task, never the worker, to
avoid two containers racing to apply the same migration). This means a
new migration ships automatically on the next deploy — there is currently
no manual approval gate before a migration runs against production data.
For a schema change you're nervous about, consider temporarily setting
`RUN_MIGRATIONS=false` on the task definition and running an
`alembic upgrade head` via `aws ecs run-task` manually instead, so you can
watch it happen.

## Pre-deployment checklist

Before pointing real users at a freshly-deployed environment, verify by
hand (none of this could be verified in the sandboxed environment this
project was built in — see each increment's notes for exactly what *was*
tested):

- [ ] `terraform plan` reviewed and applied without unexpected resource replacements
- [ ] Both ECR repos have at least one pushed image; ECS services show `RUNNING` tasks
- [ ] `GET /health` and `GET /health/deep` both return 200 through the ALB
- [ ] Register a real user, confirm the verification email arrives (or check CloudWatch logs for the logged link if SMTP isn't configured yet)
- [ ] Create a knowledge base, upload a real PDF, watch it move through every status (`pending` -> ... -> `completed`) — the single best end-to-end smoke test of the whole pipeline
- [ ] Ask it a question grounded in that document and confirm you get a cited, streamed answer
- [ ] Ask it something NOT in the document and confirm you get the configured "couldn't find that" message, not a hallucinated answer
- [ ] Confirm ClamAV is actually scanning (check its container logs for a completed virus database sync — can take several minutes on first boot)
- [ ] If you need Hindi OCR, test it directly — never verified end-to-end (no Devanagari test font was available in this sandbox)
- [ ] Log in as an admin, confirm the Admin panel shows real user/document counts and that a regular user gets a 403 on `/api/admin/*`
