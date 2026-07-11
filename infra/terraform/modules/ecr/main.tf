variable "project_name" {
  type = string
}

resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}-backend"
  image_tag_mutability = "IMMUTABLE" # forces CI to push a new tag per build — never overwrite a deployed tag

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${var.project_name}-frontend"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep only the last 20 images per repo — unbounded image history costs
# storage for no benefit once CI/CD is reliably tagging by commit SHA.
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "expire images beyond the last 20"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "frontend" {
  repository = aws_ecr_repository.frontend.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "expire images beyond the last 20"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

output "backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}
output "frontend_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}
output "backend_repository_arn" {
  value = aws_ecr_repository.backend.arn
}
output "frontend_repository_arn" {
  value = aws_ecr_repository.frontend.arn
}
