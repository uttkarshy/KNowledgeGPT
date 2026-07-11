terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Remote state — uncomment and fill in after creating the state bucket
  # and lock table once, by hand, outside Terraform (a classic
  # chicken-and-egg problem: state storage can't be managed by the state
  # it stores). See ../../README.md for the one-time setup commands.
  #
  # backend "s3" {
  #   bucket         = "knowledgegpt-terraform-state-CHANGE-ME"
  #   key            = "production/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "knowledgegpt-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}
