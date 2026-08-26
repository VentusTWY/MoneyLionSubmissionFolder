# Workload-owned AWS infrastructure

This directory contains a representative Terraform foundation for the loan-risk
ML workload. It demonstrates the application's cloud integration contract; it
does not claim ownership of the company's shared MLOps platform.

## Provisioned here

- A private, encrypted and versioned S3 bucket for immutable model bundles and
  evaluation evidence.
- An immutable ECR repository with push scanning and image retention.
- An encrypted SNS topic shared by service alarms and model-quality events.
- Separate CloudWatch log groups for serving and training, plus a representative
  custom service-error alarm.
- A least-privilege workload policy that the platform team can attach to an
  existing EKS IRSA or SageMaker execution role.

## Expected from the shared MLOps platform

- VPC, subnets, security groups and private endpoints.
- EKS clusters, ingress, workload identity and autoscaling.
- SageMaker domain, training runtime, Model Registry and real-time endpoint.
- MWAA/EventBridge orchestration and organisation-wide CI/CD controls.
- Amazon Q Developer in chat applications and the Slack `#ml-alerts` channel.

Those resources should be consumed through agreed platform outputs or remote
state rather than recreated by this workload repository.

## Usage

Authentication and the Terraform state backend must be configured through the
organisation's normal AWS workflow. Local state is suitable only for a disposable
demo account.

```bash
cd infra/terraform
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -var-file=environments/dev.tfvars
```

No AWS resources are created until an authorised operator runs `terraform apply`.
The generated `artifact_bucket_uri` can later supply `MODEL_REGISTRY_URI` once
the production S3 registry adapter described in the root README is implemented.

The custom `LoanRisk/Service` metric must include the `Environment` dimension.
Model-quality jobs can publish alerts directly to the exported SNS topic ARN.
