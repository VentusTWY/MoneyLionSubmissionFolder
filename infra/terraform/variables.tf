variable "aws_region" {
  description = "AWS region for workload-owned resources."
  type        = string
  default     = "eu-west-2"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "project_name" {
  description = "Short name used to identify workload resources."
  type        = string
  default     = "loan-risk"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.project_name))
    error_message = "project_name must be 3-31 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "artifact_retention_days" {
  description = "Days before non-current artifact versions are expired."
  type        = number
  default     = 90

  validation {
    condition     = var.artifact_retention_days >= 30
    error_message = "artifact_retention_days must be at least 30."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention for workload logs."
  type        = number
  default     = 30
}

variable "service_error_threshold" {
  description = "Number of service errors in five minutes that triggers an alarm."
  type        = number
  default     = 5
}

variable "additional_tags" {
  description = "Extra tags applied to every supported resource."
  type        = map(string)
  default     = {}
}
