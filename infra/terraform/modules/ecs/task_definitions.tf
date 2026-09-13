locals {
  # Shared env/secrets shape for both the API and worker task definitions —
  # they run the identical image, just with a different `command`, so their
  # runtime configuration should never drift from each other except where
  # explicitly overridden (see RUN_MIGRATIONS below).
  backend_common_env = [
    { name = "ENVIRONMENT", value = "production" },
    { name = "REDIS_URL", value = "redis://${var.redis_endpoint}:6379/0" },
    { name = "S3_BUCKET_NAME", value = var.uploads_bucket_name },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "CORS_ALLOWED_ORIGINS", value = jsonencode([var.frontend_public_url]) },
  ]

  backend_common_secrets = [
    { name = "DATABASE_URL", valueFrom = "${var.app_secrets_arn}:DATABASE_URL::" },
    { name = "JWT_SECRET_KEY", valueFrom = "${var.app_secrets_arn}:JWT_SECRET_KEY::" },
    { name = "OPENAI_API_KEY", valueFrom = "${var.app_secrets_arn}:OPENAI_API_KEY::" },
  ]
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name         = "backend"
      image        = "${var.backend_ecr_url}:${var.backend_image_tag}"
      essential    = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = concat(local.backend_common_env, [
        { name = "RUN_MIGRATIONS", value = "true" }, # only the API task runs migrations, never the worker
      ])
      secrets = local.backend_common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.backend_log_group
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "2048" # workers do CPU-heavy OCR/extraction work — sized larger than the API task
  memory                   = "4096"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${var.backend_ecr_url}:${var.backend_image_tag}"
      essential = true
      command   = ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
      environment = concat(local.backend_common_env, [
        { name = "RUN_MIGRATIONS", value = "false" },
      ])
      secrets = local.backend_common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.worker_log_group
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name         = "frontend"
      image        = "${var.frontend_ecr_url}:${var.frontend_image_tag}"
      essential    = true
      portMappings = [{ containerPort = 3000, protocol = "tcp" }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.frontend_log_group
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "frontend"
        }
      }
    }
  ])
}
