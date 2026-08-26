output "artifact_bucket_name" {
  description = "Versioned S3 bucket for model artifacts and evaluation evidence."
  value       = aws_s3_bucket.model_artifacts.id
}

output "artifact_bucket_uri" {
  description = "S3 URI used by the production model-registry adapter."
  value       = "s3://${aws_s3_bucket.model_artifacts.id}/registry"
}

output "ecr_repository_url" {
  description = "Repository for versioned training and serving images."
  value       = aws_ecr_repository.workload.repository_url
}

output "ml_alerts_topic_arn" {
  description = "SNS topic to connect to the shared Slack alert integration."
  value       = aws_sns_topic.ml_alerts.arn
}

output "workload_policy_arn" {
  description = "Policy for attachment to platform-owned IRSA or SageMaker roles."
  value       = aws_iam_policy.workload.arn
}

output "cloudwatch_log_groups" {
  description = "Workload log groups consumed by the shared observability platform."
  value = {
    serving  = aws_cloudwatch_log_group.serving.name
    training = aws_cloudwatch_log_group.training.name
  }
}
