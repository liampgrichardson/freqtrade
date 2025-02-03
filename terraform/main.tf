# Define the provider
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = var.global_tags
  }
}

# TF state bucket
terraform {
  backend "s3" {
    bucket = "my-tfstate-bucket-001" # Replace with your S3 bucket name
    key    = "terraform-bot.tfstate"
    region = "eu-west-1"             # Replace with your AWS region
  }
}

# Reference the existing ECR repository
data "aws_ecr_repository" "existing_repository" {
  name = var.ecr_repository_name # variable is received by gh actions workflow
}

# Output image tag
output "image_tag" {
  description = "The image tag for the deployed application"
  value       = var.image_tag
  sensitive   = true
}
