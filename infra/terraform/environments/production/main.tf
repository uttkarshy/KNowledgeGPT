module "network" {
  source       = "../../modules/network"
  project_name = var.project_name
}

module "security" {
  source       = "../../modules/security"
  project_name = var.project_name
  vpc_id       = module.network.vpc_id
}

module "storage" {
  source       = "../../modules/storage"
  project_name = var.project_name
  environment  = "production"
}

module "database" {
  source             = "../../modules/database"
  project_name       = var.project_name
  private_subnet_ids = module.network.private_subnet_ids
  security_group_id  = module.security.rds_sg_id
  instance_class     = var.db_instance_class
  master_password    = var.db_master_password
}

module "cache" {
  source             = "../../modules/cache"
  project_name       = var.project_name
  private_subnet_ids = module.network.private_subnet_ids
  security_group_id  = module.security.redis_sg_id
  node_type          = var.redis_node_type
}

module "secrets" {
  source         = "../../modules/secrets"
  project_name   = var.project_name
  database_url   = "postgresql+asyncpg://knowledgegpt:${var.db_master_password}@${module.database.database_url_no_credentials}"
  jwt_secret_key = var.jwt_secret_key
  openai_api_key = var.openai_api_key
}

module "ecr" {
  source       = "../../modules/ecr"
  project_name = var.project_name
}

module "alb" {
  source              = "../../modules/alb"
  project_name        = var.project_name
  vpc_id              = module.network.vpc_id
  public_subnet_ids   = module.network.public_subnet_ids
  security_group_id   = module.security.alb_sg_id
  acm_certificate_arn = var.acm_certificate_arn
}

module "cloudwatch" {
  source       = "../../modules/cloudwatch"
  project_name = var.project_name
}

module "github_oidc" {
  count  = var.github_repo != "" ? 1 : 0
  source = "../../modules/github_oidc"

  project_name                = var.project_name
  github_repo                 = var.github_repo
  backend_ecr_arn             = module.ecr.backend_repository_arn
  frontend_ecr_arn            = module.ecr.frontend_repository_arn
  ecs_task_execution_role_arn = module.ecs.task_execution_role_arn
  ecs_task_role_arn           = module.ecs.task_role_arn
}

module "ecs" {
  source = "../../modules/ecs"

  project_name       = var.project_name
  aws_region         = var.aws_region
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  ecs_service_sg_id  = module.security.ecs_service_sg_id
  ecs_worker_sg_id   = module.security.ecs_worker_sg_id

  backend_ecr_url    = module.ecr.backend_repository_url
  frontend_ecr_url   = module.ecr.frontend_repository_url
  backend_image_tag  = var.backend_image_tag
  frontend_image_tag = var.frontend_image_tag

  backend_target_group_arn  = module.alb.backend_target_group_arn
  frontend_target_group_arn = module.alb.frontend_target_group_arn

  app_secrets_arn     = module.secrets.secret_arn
  uploads_bucket_arn  = module.storage.bucket_arn
  uploads_bucket_name = module.storage.bucket_name
  redis_endpoint      = module.cache.primary_endpoint

  backend_log_group  = module.cloudwatch.backend_log_group_name
  worker_log_group   = module.cloudwatch.worker_log_group_name
  frontend_log_group = module.cloudwatch.frontend_log_group_name

  backend_desired_count  = var.backend_desired_count
  worker_desired_count   = var.worker_desired_count
  frontend_desired_count = var.frontend_desired_count

  frontend_public_url = var.domain_name != "" ? "https://${var.domain_name}" : "http://${module.alb.alb_dns_name}"
}
