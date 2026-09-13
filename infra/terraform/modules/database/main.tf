variable "project_name" {
  type = string
}
variable "private_subnet_ids" {
  type = list(string)
}
variable "security_group_id" {
  type = string
}
variable "instance_class" {
  type    = string
  default = "db.r6g.large"
}
variable "allocated_storage_gb" {
  type    = number
  default = 100
}
variable "multi_az" {
  type    = bool
  default = true
}
variable "master_password" {
  type      = string
  sensitive = true
}
variable "backup_retention_days" {
  type    = number
  default = 14
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnets"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "${var.project_name}-db-subnets" }
}

# pgvector ships as an available extension on RDS PostgreSQL 15.4+/16.1+ by
# default — no custom parameter group flag is required to enable the
# extension itself, only the `CREATE EXTENSION vector;` statement our
# Alembic migration (0001_initial_schema) already runs. This parameter
# group exists for connection/performance tuning, not extension enablement.
resource "aws_db_parameter_group" "main" {
  name   = "${var.project_name}-pg16"
  family = "postgres16"

  parameter {
    name  = "log_min_duration_statement"
    value = "1000" # log queries slower than 1s — helps catch missing-index regressions
  }
}

resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16.4"
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.allocated_storage_gb * 3 # storage autoscaling ceiling
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "knowledgegpt"
  username = "knowledgegpt"
  password = var.master_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]
  parameter_group_name   = aws_db_parameter_group.main.name

  multi_az                  = var.multi_az
  publicly_accessible       = false
  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project_name}-db-final-snapshot"

  backup_retention_period = var.backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "mon:04:30-mon:05:30"

  performance_insights_enabled = true

  tags = { Name = "${var.project_name}-db" }
}

output "endpoint" {
  value = aws_db_instance.main.address
}
output "port" {
  value = aws_db_instance.main.port
}
output "database_url_no_credentials" {
  description = "Host:port/dbname — combine with the master password (kept out of state/outputs) to build DATABASE_URL"
  value       = "${aws_db_instance.main.address}:${aws_db_instance.main.port}/knowledgegpt"
}
