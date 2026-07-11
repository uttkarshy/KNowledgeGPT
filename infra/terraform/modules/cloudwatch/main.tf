variable "project_name" {
  type = string
}
variable "alarm_sns_topic_arn" {
  type    = string
  default = ""
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}/backend"
  retention_in_days = 30
}
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}/worker"
  retention_in_days = 30
}
resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.project_name}/frontend"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_metric_filter" "backend_errors" {
  name           = "${var.project_name}-backend-error-count"
  log_group_name = aws_cloudwatch_log_group.backend.name
  pattern        = "ERROR"

  metric_transformation {
    name      = "BackendErrorCount"
    namespace = var.project_name
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "backend_error_rate" {
  alarm_name          = "${var.project_name}-backend-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods   = 2
  metric_name         = aws_cloudwatch_log_metric_filter.backend_errors.metric_transformation[0].name
  namespace           = var.project_name
  period              = 300
  statistic           = "Sum"
  threshold           = 20
  alarm_description   = "More than 20 ERROR-level log lines in 5 minutes"
  alarm_actions       = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  treat_missing_data  = "notBreaching"
}

output "backend_log_group_name" {
  value = aws_cloudwatch_log_group.backend.name
}
output "worker_log_group_name" {
  value = aws_cloudwatch_log_group.worker.name
}
output "frontend_log_group_name" {
  value = aws_cloudwatch_log_group.frontend.name
}
