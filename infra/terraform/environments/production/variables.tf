variable "project_name" {
  type    = string
  default = "knowledgegpt"
}
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "db_master_password" {
  type        = string
  sensitive   = true
  description = "Set via TF_VAR_db_master_password env var or a .tfvars file that is NEVER committed — do not put real secrets in .tfvars checked into git."
}
variable "jwt_secret_key" {
  type        = string
  sensitive   = true
  description = "Generate with: openssl rand -hex 32. Set via TF_VAR_jwt_secret_key."
}
variable "openai_api_key" {
  type        = string
  sensitive   = true
  default     = ""
  description = "Optional at apply time — can also be set directly in Secrets Manager post-apply if you'd rather not have it touch Terraform state at all."
}

variable "github_repo" {
  type        = string
  default     = ""
  description = "e.g. \"my-org/knowledgegpt\" — required for GitHub Actions CI/CD to be able to assume the deploy role. Leave empty to skip creating the OIDC role."
}

variable "domain_name" {
  type        = string
  default     = ""
  description = "e.g. app.knowledgegpt.example.com — leave empty to skip Route53/ACM/CloudFront and use the ALB's default DNS name directly."
}
variable "acm_certificate_arn" {
  type        = string
  default     = ""
  description = "ACM certificate ARN for domain_name, must be issued in the SAME region as the ALB (us-east-1 requirement is only for CloudFront-attached certs, not ALB certs)."
}

variable "backend_image_tag" {
  type    = string
  default = "latest"
}
variable "frontend_image_tag" {
  type    = string
  default = "latest"
}

variable "backend_desired_count" {
  type    = number
  default = 2
}
variable "worker_desired_count" {
  type    = number
  default = 2
}
variable "frontend_desired_count" {
  type    = number
  default = 2
}

variable "db_instance_class" {
  type    = string
  default = "db.r6g.large"
}
variable "redis_node_type" {
  type    = string
  default = "cache.r6g.large"
}
