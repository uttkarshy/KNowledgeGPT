variable "project_name" {
  type = string
}
variable "environment" {
  type = string
}

resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project_name}-uploads-${var.environment}"
  tags   = { Name = "${var.project_name}-uploads" }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Disabled" # deliberately off — originals aren't meant to persist at all, see lifecycle rule below
  }
}

# Safety net for the "no permanent file storage" rule: even though the
# application deletes each object itself right after successful embedding
# (see app/services/embedding/pipeline.py), this lifecycle rule guarantees
# that any object orphaned by a crashed/stuck pipeline run (never got to
# the delete step) is force-expired after 7 days rather than accumulating
# indefinitely and silently violating the storage policy.
resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "expire-abandoned-uploads"
    status = "Enabled"
    filter {}
    expiration {
      days = 7
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_methods = ["PUT"]
    allowed_origins = ["*"] # tightened to the real frontend origin at deploy time via var if desired
    allowed_headers = ["Content-Type"]
    max_age_seconds = 3000
  }
}

output "bucket_name" {
  value = aws_s3_bucket.uploads.bucket
}
output "bucket_arn" {
  value = aws_s3_bucket.uploads.arn
}
