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
    key    = "kafka-test-tf-key.tfstate"
    region = "eu-west-1"
  }
}

# VPC + networking
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public_rt.id
}

# Security Group for EC2 & MSK
resource "aws_security_group" "bastion_sg" {
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # ⚠️ Adjust to your IP for security
  }

  ingress {
    from_port   = 9098
    to_port     = 9098
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # For local testing via SSH tunnel
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# MSK IAM role
resource "aws_iam_role" "msk_broker_role" {
  name = "MSKBrokerIAMRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "kafka.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_msk_cluster" "msk" {
  cluster_name           = "freqtrade-msk-cluster"
  kafka_version          = "2.8.1"
  number_of_broker_nodes = 2

  broker_node_group_info {
    instance_type   = "kafka.t3.small"
    client_subnets  = [aws_subnet.public.id]
    security_groups = [aws_security_group.bastion_sg.id]
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  client_authentication {
    sasl {
      iam = true
    }
  }
}

# Bastion host
resource "aws_key_pair" "bastion_key" {
  key_name   = "bastion-key"
  public_key = file("${path.module}/ec2_github_actions_key.pub")
}

resource "aws_instance" "bastion" {
  ami                    = "ami-0c7c4e3c6b4941f0f" # Amazon Linux 2 (eu-west-1)
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public.id
  security_groups        = [aws_security_group.bastion_sg.name]
  key_name               = aws_key_pair.bastion_key.key_name
  associate_public_ip_address = true

  tags = {
    Name = "MSK-Bastion"
  }
}
