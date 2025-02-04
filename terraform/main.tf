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
  name = var.ecr_repository_name # Variable received from GitHub Actions workflow
}

# Store the SSH Key Pair in AWS
resource "aws_key_pair" "ec2_key" {
  key_name   = "github-actions-key"
  public_key = var.ec2_ssh_public_key
}

# Find the latest Ubuntu AMI (for free-tier eligible t2.micro)
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical (Ubuntu) official owner ID

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

# Create a VPC
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

# Create a private subnet
resource "aws_subnet" "private_subnet" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = false
}

# Create an Internet Gateway (for outbound traffic)
resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
}

# Create a NAT Gateway (to allow outbound traffic while keeping EC2 private)
resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.private_subnet.id
}

# Route table for private subnet (uses NAT for internet access)
resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }
}

resource "aws_route_table_association" "private_assoc" {
  subnet_id      = aws_subnet.private_subnet.id
  route_table_id = aws_route_table.private_rt.id
}

# Security group for EC2 (SSH from GitHub Actions & allow outbound traffic)
resource "aws_security_group" "ec2_sg" {
  vpc_id = aws_vpc.main.id

  # Allow SSH from GitHub Actions (Dynamic IPs)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Wide open, but can be locked down with GitHub OIDC later
  }

  # Allow all outbound traffic (for Docker containers)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# IAM Role for EC2 instance (Allows access to AWS Timestream)
resource "aws_iam_role" "ec2_role" {
  name = "ec2-timestream-role"

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

# Attach policy for AWS Timestream access
resource "aws_iam_policy" "timestream_policy" {
  name        = "TimestreamAccessPolicy"
  description = "Allows EC2 instance to query AWS Timestream"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["timestream:Select", "timestream:DescribeEndpoints"]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "timestream_attach" {
  policy_arn = aws_iam_policy.timestream_policy.arn
  role       = aws_iam_role.ec2_role.name
}

# Instance profile for EC2
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "ec2-instance-profile"
  role = aws_iam_role.ec2_role.name
}

# Create EC2 instance (Free-tier t2.micro)
resource "aws_instance" "my_ec2" {
  ami                    = data.aws_ami.ubuntu.id  # Dynamically get latest Ubuntu AMI
  instance_type          = "t2.micro"
  subnet_id              = aws_subnet.private_subnet.id
  key_name               = aws_key_pair.ec2_key.key_name
  security_groups        = [aws_security_group.ec2_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

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

# Output the image tag
output "image_tag" {
  description = "The image tag for the deployed application"
  value       = var.image_tag
  sensitive   = true
}
