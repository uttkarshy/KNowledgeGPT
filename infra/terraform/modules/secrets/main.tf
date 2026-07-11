variable "project_name" {
  type = string
}
variable "database_url" {
  type      = string
  sensitive = true
}
variable "jwt_secret_key" {
  type      = string
  sensitive = true
}
variable "openai_api_key" {
  type      = string
  sensitive = true
  default   = "" # populated manually post-apply (see README) — never committed to state via a var default in real use
}

# Single JSON secret holding everything the ECS task definitions inject as
# environment variables via `secrets` (not `environment`) blocks — keeps
# all sensitive config in exactly one place to rotate, rather than scattered
# across N individual secrets.
resource "aws_secretsmanager_secret" "app_secrets" {
  name        = "${var.project_name}/app-secrets"
  description = "DATABASE_URL, JWT_SECRET_KEY, OPENAI_API_KEY, etc. for the KnowledgeGPT backend/worker tasks"
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    DATABASE_URL   = var.database_url
    JWT_SECRET_KEY = var.jwt_secret_key
    OPENAI_API_KEY = var.openai_api_key
  })

  lifecycle {
    # Prevents `terraform apply` from clobbering values rotated directly in
    # the AWS console/CLI (e.g. a rotated OPENAI_API_KEY) with stale
    # Terraform variable values on the next apply.
    ignore_changes = [secret_string]
  }
}

output "secret_arn" {
  value = aws_secretsmanager_secret.app_secrets.arn
}
