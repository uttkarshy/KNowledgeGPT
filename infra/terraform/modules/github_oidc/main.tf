variable "project_name" {
  type = string
}
variable "github_repo" {
  type        = string
  description = "e.g. \"my-org/knowledgegpt\" — restricts which repo (and by extension, which workflow runs) can assume this role."
}
variable "backend_ecr_arn" {
  type = string
}
variable "frontend_ecr_arn" {
  type = string
}
variable "ecs_task_execution_role_arn" {
  type = string
}
variable "ecs_task_role_arn" {
  type = string
}

data "aws_caller_identity" "current" {}

# GitHub's OIDC thumbprint is stable and documented by GitHub; if this ever
# needs rotating, AWS's own docs / the aws_iam_openid_connect_provider
# resource can fetch it automatically instead of hardcoding, but pinning it
# explicitly here avoids a surprise diff on unrelated applies.
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Restricts to THIS repo's branches/tags only — not forks, not other repos.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:*"]
    }
  }
}

resource "aws_iam_role" "github_actions_deploy" {
  name               = "${var.project_name}-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_assume_role.json
}

data "aws_iam_policy_document" "deploy_permissions" {
  statement {
    sid       = "ECRAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "ECRPushPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
    ]
    resources = [var.backend_ecr_arn, var.frontend_ecr_arn]
  }
  statement {
    sid = "ECSDeploy"
    actions = [
      "ecs:UpdateService",
      "ecs:DescribeServices",
      "ecs:DescribeTaskDefinition",
      "ecs:RegisterTaskDefinition",
    ]
    resources = ["*"] # ECS task def/service actions don't support fine-grained resource ARNs consistently; scoped by role trust policy instead
  }
  statement {
    sid       = "PassTaskRoles"
    actions   = ["iam:PassRole"]
    resources = [var.ecs_task_execution_role_arn, var.ecs_task_role_arn]
  }
}

resource "aws_iam_role_policy" "deploy_permissions" {
  name   = "${var.project_name}-github-actions-deploy-permissions"
  role   = aws_iam_role.github_actions_deploy.id
  policy = data.aws_iam_policy_document.deploy_permissions.json
}

output "deploy_role_arn" {
  value = aws_iam_role.github_actions_deploy.arn
}
