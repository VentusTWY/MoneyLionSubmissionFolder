locals {
  name = "${var.project_name}-${var.environment}"
  common_tags = merge(
    {
      Application = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "ML Engineering"
    },
    var.additional_tags,
  )
}

# Immutable model bundles and evaluation evidence. SageMaker Model Registry
# stores the governed model version and references artifacts in this bucket.
resource "aws_s3_bucket" "model_artifacts" {
  bucket_prefix = "${local.name}-model-artifacts-"
}

resource "aws_s3_bucket_versioning" "model_artifacts" {
  bucket = aws_s3_bucket.model_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "model_artifacts" {
  bucket = aws_s3_bucket.model_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "model_artifacts" {
  bucket = aws_s3_bucket.model_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "model_artifacts" {
  bucket = aws_s3_bucket.model_artifacts.id

  rule {
    id     = "expire-noncurrent-artifacts"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = var.artifact_retention_days
    }
  }

  depends_on = [aws_s3_bucket_versioning.model_artifacts]
}

# Versioned training and serving container images. Deployment into the shared
# EKS/SageMaker platform is deliberately owned by the platform pipeline.
resource "aws_ecr_repository" "workload" {
  name                 = local.name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "workload" {
  repository = aws_ecr_repository.workload.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Retain the latest 30 workload images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Both service alarms and model-quality jobs publish into this topic. The shared
# MLOps platform owns the Amazon Q Developer/Slack channel integration.
resource "aws_sns_topic" "ml_alerts" {
  name              = "${local.name}-ml-alerts"
  kms_master_key_id = "alias/aws/sns"
}

resource "aws_cloudwatch_log_group" "serving" {
  name              = "/${var.project_name}/${var.environment}/serving"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "training" {
  name              = "/${var.project_name}/${var.environment}/training"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_metric_alarm" "service_errors" {
  alarm_name          = "${local.name}-service-errors"
  alarm_description   = "Loan-risk serving errors exceeded the five-minute threshold."
  namespace           = "LoanRisk/Service"
  metric_name         = "Errors"
  dimensions          = { Environment = var.environment }
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  period              = 300
  statistic           = "Sum"
  threshold           = var.service_error_threshold
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ml_alerts.arn]
  ok_actions          = [aws_sns_topic.ml_alerts.arn]
}

# This workload policy is an integration contract. The MLOps team attaches it
# to the existing IRSA/SageMaker execution roles in the shared platform.
data "aws_iam_policy_document" "workload" {
  statement {
    sid       = "ListModelArtifacts"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.model_artifacts.arn]
  }

  statement {
    sid = "ReadWriteModelArtifactObjects"
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.model_artifacts.arn}/*"]
  }

  statement {
    sid = "PublishMLAlerts"
    actions = [
      "sns:Publish",
    ]
    resources = [aws_sns_topic.ml_alerts.arn]
  }

  statement {
    sid = "WriteWorkloadLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      aws_cloudwatch_log_group.serving.arn,
      "${aws_cloudwatch_log_group.serving.arn}:*",
      aws_cloudwatch_log_group.training.arn,
      "${aws_cloudwatch_log_group.training.arn}:*",
    ]
  }

  statement {
    sid       = "WriteWorkloadMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["LoanRisk/Service", "LoanRisk/ModelQuality"]
    }
  }
}

resource "aws_iam_policy" "workload" {
  name        = "${local.name}-workload"
  description = "Workload-level access for loan-risk training, serving, and alert publication."
  policy      = data.aws_iam_policy_document.workload.json
}
