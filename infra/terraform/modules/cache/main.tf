variable "project_name" {
  type = string
}
variable "private_subnet_ids" {
  type = list(string)
}
variable "security_group_id" {
  type = string
}
variable "node_type" {
  type    = string
  default = "cache.r6g.large"
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-redis-subnets"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.project_name}-redis"
  description          = "Celery broker/result backend + rate-limit counters"

  engine         = "redis"
  engine_version = "7.1"
  node_type      = var.node_type

  num_cache_clusters = 2 # primary + 1 replica for HA
  automatic_failover_enabled = true

  subnet_group_name = aws_elasticache_subnet_group.main.name
  security_group_ids = [var.security_group_id]

  at_rest_encryption_enabled = true
  # NOTE: transit encryption (TLS) is intentionally left off for now — the
  # application's REDIS_URL construction (app/core/config.py) doesn't yet
  # handle `rediss://` + AUTH token plumbing. Enabling this is a legitimate
  # follow-up hardening step, but should ship together with that app-side
  # change rather than being turned on here without it.
  transit_encryption_enabled = false

  tags = { Name = "${var.project_name}-redis" }
}

output "primary_endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}
output "port" {
  value = 6379
}
