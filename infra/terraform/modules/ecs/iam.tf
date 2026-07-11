resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ---------------- Task EXECUTION role ----------------
# Used by the ECS agent itself: pull images from ECR, write to CloudWatch
# Logs, and fetch Secrets Manager values to inject as container env vars.
# This is NOT the role the application code runs as.
data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${var.project_name}-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "task_execution_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.app_secrets_arn]
  }
}

resource "aws_iam_role_policy" "task_execution_secrets" {
  name   = "${var.project_name}-read-app-secrets"
  role   = aws_iam_role.task_execution.id
  policy = data.aws_iam_policy_document.task_execution_secrets.json
}

# ---------------- Task role ----------------
# What the APPLICATION CODE runs as (boto3 inside app/core/aws.py picks
# these credentials up automatically via the container's metadata
# endpoint — no access keys are ever baked into the image or env).
resource "aws_iam_role" "task" {
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

data "aws_iam_policy_document" "task_s3_access" {
  statement {
    sid = "UploadsBucketObjectAccess"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:HeadObject",
    ]
    resources = ["${var.uploads_bucket_arn}/*"]
  }
}

resource "aws_iam_role_policy" "task_s3" {
  name   = "${var.project_name}-task-s3-access"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_s3_access.json
}
