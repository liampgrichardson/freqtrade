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
    bucket = "my-tfstate-bucket-001"
    key    = "terraform-bot.tfstate"
    region = "eu-west-1"
  }
}

# Enable DNS support for VPC
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  enable_dns_support   = true   # Ensures instances can resolve domain names
  enable_dns_hostnames = true   # Allows public DNS names for public instances
}

# Find the latest Ubuntu AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

# Create a Public Subnet
resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  map_public_ip_on_launch = true
}

# Create an Internet Gateway for public access
resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
}

# Route table for the public subnet
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_rt.id
}

# Security group for EC2 (SSH only, no other inbound access)
resource "aws_security_group" "ec2_sg" {
  vpc_id = aws_vpc.main.id

  # Allow SSH for debugging purposes
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow all outbound traffic (needed for updates, package installs, etc.)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# IAM Role for EC2 instance
resource "aws_iam_role" "ec2_role" {
  name = "ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

# Attach policy for AWS dynamodb access
resource "aws_iam_policy" "ec2_dynamodb_policy" {
  name        = "FreqtradeEC2DynamoDBPolicy"
  description = "Policy to allow ECS tasks to interact with DynamoDB"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:DescribeTable"
        ],
        Resource = "*" # Ideally scope to the specific table ARN
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "timestream_attach" {
  policy_arn = aws_iam_policy.ec2_dynamodb_policy.arn
  role       = aws_iam_role.ec2_role.name
}

# Attach policy for Amazon ECR access
resource "aws_iam_policy" "ecr_policy" {
  name        = "ECRAccessPolicy"
  description = "Allows EC2 instance to pull images from Amazon ECR"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecr_attach" {
  policy_arn = aws_iam_policy.ecr_policy.arn
  role       = aws_iam_role.ec2_role.name
}

# Instance profile for EC2
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "ec2-instance-profile"
  role = aws_iam_role.ec2_role.name
}

# Create EC2 instance (Publicly accessible with only SSH allowed)
resource "aws_instance" "my_ec2" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t2.micro"
  subnet_id              = aws_subnet.public_subnet.id  # Public subnet
  security_groups        = [aws_security_group.ec2_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  associate_public_ip_address = true  # Ensures the instance gets a public IP

  user_data = templatefile("${path.module}/setup.sh.tpl", {
  github_repo   = var.github_repo,      # e.g., "myuser/freqtrade"
  github_ref    = var.github_ref,       # e.g., "main"
  ecr_repo_url  = var.ecr_repo_url,
  image_tag     = var.image_tag,
  aws_region    = var.aws_region
  })

  tags = {
    Name = "DockerHost"
  }
}

# Output the private IP of the EC2 instance
output "ec2_private_ip" {
  description = "The private IP address of the EC2 instance"
  value       = aws_instance.my_ec2.private_ip
  sensitive   = true
}

# Output the public IP of the EC2 instance
output "ec2_public_ip" {
  description = "The public IP address of the EC2 instance"
  value       = aws_instance.my_ec2.public_ip
  sensitive   = true
}

# Output the EC2 instance ID
output "ec2_instance_id" {
  description = "The ID of the EC2 instance"
  value       = aws_instance.my_ec2.id
  sensitive   = true
}
