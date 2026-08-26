aws_region              = "eu-west-2"
environment             = "dev"
project_name            = "loan-risk"
artifact_retention_days = 90
log_retention_days      = 30
service_error_threshold = 5

additional_tags = {
  CostCentre = "ml-interview-demo"
}
