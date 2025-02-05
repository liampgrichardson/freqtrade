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

variable "ec2_ssh_public_key" {
  description = "Public SSH key for EC2 access"
  type        = string
}
