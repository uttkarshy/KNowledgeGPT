# AWS deployment (Terraform + ECS Fargate)

## Architecture
Route53 (optional) → CloudFront (not yet built, see below) → ALB → ECS Fargate
(backend API + Celery workers + Next.js frontend, each as separate services)
→ RDS PostgreSQL (pgvector) + ElastiCache Redis, with S3 for transient
uploads, Secrets Manager for credentials, and CloudWatch for logs/alarms.

**Not yet built**: a CloudFront distribution in front of the ALB. Your
original spec's diagram included it; it was deferred because CloudFront
in front of an ALB that's already doing TLS termination and both a REST
API and an SSE-streaming app is a real design decision (cache behaviors
need to explicitly bypass caching for `/api/*` and disable buffering for
the streaming endpoint) rather than a boilerplate add — happy to build it
as a follow-up once you confirm you want edge caching specifically (e.g.
for global user latency) rather than just TLS/CDN.

## One-time setup (before first `terraform apply`)

1. **Remote state** (chicken-and-egg — must exist before Terraform can use it):
   ```bash
   aws s3 mb s3://knowledgegpt-terraform-state-<unique-suffix>
   aws dynamodb create-table --table-name knowledgegpt-terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST
   ```
   Then uncomment and fill in the `backend "s3"` block in
   `environments/production/providers.tf`.

2. **ACM certificate** (if you have a domain): request/validate one in the
   same region as the ALB, pass its ARN as `acm_certificate_arn`.

3. **Secrets** — never commit real values. Set as environment variables
   before running Terraform:
   ```bash
   export TF_VAR_db_master_password="$(openssl rand -base64 24)"
   export TF_VAR_jwt_secret_key="$(openssl rand -hex 32)"
   export TF_VAR_openai_api_key="sk-..."
   ```

4. **GitHub Actions OIDC**: set `github_repo = "your-org/your-repo"` in a
   `.tfvars` file, then after `apply`, copy the `deploy_role_arn` output
   into the GitHub repo's Settings → Secrets and variables → Actions →
   Variables as `AWS_DEPLOY_ROLE_ARN`, and set `PUBLIC_API_BASE_URL` to
   your ALB DNS name or domain.

## Apply

```bash
cd environments/production
terraform init
terraform plan   # review carefully — this creates real, billable AWS resources
terraform apply
```

First apply will fail to find any images in the two ECR repos it just
created — that's expected. Push once manually (or trigger the `deploy`
GitHub Actions workflow) before the ECS services can start successfully:

```bash
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -t <account>.dkr.ecr.<region>.amazonaws.com/knowledgegpt-backend:latest ./backend
docker push <account>.dkr.ecr.<region>.amazonaws.com/knowledgegpt-backend:latest
# ...same for frontend
```

## What's verified vs. not

Every module's HCL syntax was validated with `terraform-config-inspect`
(HashiCorp's own parsing tool), and every cross-module variable/output
reference was cross-checked programmatically against each module's actual
declared variables and outputs — this caught two real copy-paste bugs
(a clobbered `module "ecs" {` block header, and an ECR *repository URL*
being passed where an IAM policy needed the ECR *ARN*), both fixed and
re-verified.

**What this could NOT verify**, since there is no Docker daemon, AWS
credentials, or network access to AWS APIs in the sandbox this was built
in: an actual `terraform plan`/`apply` against real AWS, and therefore
whether every resource argument is valid for the current AWS provider
version, whether IAM permissions are sufficient in practice, or whether
the whole stack actually stands up and serves traffic end-to-end. Run
`terraform plan` yourself as the real first checkpoint before `apply`.
