output "alb_dns_name" {
  value       = module.alb.alb_dns_name
  description = "Point your domain's CNAME/A-record (or use this directly) at this hostname."
}

output "backend_ecr_repository_url" {
  value = module.ecr.backend_repository_url
}
output "frontend_ecr_repository_url" {
  value = module.ecr.frontend_repository_url
}

output "database_endpoint" {
  value = module.database.endpoint
}
output "redis_endpoint" {
  value = module.cache.primary_endpoint
}
output "uploads_bucket_name" {
  value = module.storage.bucket_name
}
output "app_secrets_arn" {
  value = module.secrets.secret_arn
}
output "ecs_cluster_name" {
  value = module.ecs.cluster_id
}
