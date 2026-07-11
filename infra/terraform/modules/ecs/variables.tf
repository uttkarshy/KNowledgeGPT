variable "project_name" {
  type = string
}
variable "vpc_id" {
  type = string
}
variable "private_subnet_ids" {
  type = list(string)
}
variable "ecs_service_sg_id" {
  type = string
}
variable "ecs_worker_sg_id" {
  type = string
}
variable "backend_ecr_url" {
  type = string
}
variable "frontend_ecr_url" {
  type = string
}
variable "backend_image_tag" {
  type    = string
  default = "latest"
}
variable "frontend_image_tag" {
  type    = string
  default = "latest"
}
variable "backend_target_group_arn" {
  type = string
}
variable "frontend_target_group_arn" {
  type = string
}
variable "app_secrets_arn" {
  type = string
}
variable "uploads_bucket_arn" {
  type = string
}
variable "uploads_bucket_name" {
  type = string
}
variable "redis_endpoint" {
  type = string
}
variable "aws_region" {
  type = string
}
variable "backend_log_group" {
  type = string
}
variable "worker_log_group" {
  type = string
}
variable "frontend_log_group" {
  type = string
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

variable "frontend_public_url" {
  type    = string
  default = "http://localhost:3000"
}
