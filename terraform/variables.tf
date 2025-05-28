# AWS Region
variable "aws_region" {
  description = "The AWS region to deploy resources in, gotten from gh actions"
  type        = string
}

# Global tags
variable "global_tags" {
  description = "A map of global tags to apply to all resources"
  type        = map(string)
}

variable "github_repo" {
  type = string
}

variable "github_ref" {
  type = string
}

variable "ecr_repo" {
  type = string
}

variable "ecr_reg" {
  type = string
}

variable "image_tag" {
  type = string
}
