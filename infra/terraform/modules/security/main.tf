variable "project_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

# ---------------- ALB: only thing open to the internet ----------------
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "Allows inbound HTTPS/HTTP from the internet to the ALB"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTP from internet (redirected to HTTPS by the listener rule)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-alb-sg" }
}

# ---------------- ECS backend API + frontend: only reachable from ALB ----------------
resource "aws_security_group" "ecs_service" {
  name        = "${var.project_name}-ecs-service-sg"
  description = "ECS services (backend API, frontend) — inbound only from the ALB"
  vpc_id      = var.vpc_id

  ingress {
    description     = "From ALB only"
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"] # outbound to OpenAI API, S3, etc. via NAT gateway
  }

  tags = { Name = "${var.project_name}-ecs-service-sg" }
}

# ---------------- Celery workers: no inbound at all, outbound only ----------------
resource "aws_security_group" "ecs_worker" {
  name        = "${var.project_name}-ecs-worker-sg"
  description = "Celery workers — no inbound traffic accepted from anywhere"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-ecs-worker-sg" }
}

# ---------------- RDS: only reachable from ECS services + workers ----------------
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "PostgreSQL — inbound only from ECS service/worker security groups"
  vpc_id      = var.vpc_id

  ingress {
    description     = "From ECS backend API"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_service.id, aws_security_group.ecs_worker.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-rds-sg" }
}

# ---------------- ElastiCache Redis: same pattern ----------------
resource "aws_security_group" "redis" {
  name        = "${var.project_name}-redis-sg"
  description = "Redis — inbound only from ECS service/worker security groups"
  vpc_id      = var.vpc_id

  ingress {
    description     = "From ECS backend API and workers"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_service.id, aws_security_group.ecs_worker.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-redis-sg" }
}

output "alb_sg_id" {
  value = aws_security_group.alb.id
}
output "ecs_service_sg_id" {
  value = aws_security_group.ecs_service.id
}
output "ecs_worker_sg_id" {
  value = aws_security_group.ecs_worker.id
}
output "rds_sg_id" {
  value = aws_security_group.rds.id
}
output "redis_sg_id" {
  value = aws_security_group.redis.id
}
