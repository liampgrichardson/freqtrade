#!/bin/bash
set -e

# === CONFIG VALUES (passed from Terraform) ===
REPO_URL="https://github.com/${github_repo}.git"
REPO_BRANCH="${github_ref}"
ECR_REGISTRY="${ecr_reg}"
ECR_REPOSITORY="${ecr_repo}"
IMAGE_TAG="${image_tag}"
AWS_REGION="${aws_region}"

# === Install Docker & Tools ===
sudo apt update -y
sudo apt install -y docker.io docker-compose
sudo systemctl start docker

# Enable swap if not present
if ! swapon --show | grep -q '/swapfile'; then
  echo "Creating swapfile..."
  sudo fallocate -l 3G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile

  # Make swap persistent
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
else
  echo "Swapfile already exists."
fi

# === Check installations ===
sudo docker --version
sudo docker-compose --version

# === Clone and setup freqtrade ===
cd /home/ubuntu
git clone "$REPO_URL"
cd freqtrade/
git checkout "$REPO_BRANCH"
cd ft_userdata/
chown -R 1000:1000 user_data  # for permissions
sudo docker-compose pull
sudo docker-compose up -d

# Install AWS CLI
sudo apt-get install -y awscli

# === ECR Login and container run ===
aws ecr get-login-password --region "$AWS_REGION" | sudo docker login --username AWS --password-stdin "$ECR_REGISTRY"
sudo docker pull "$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG"
sudo docker run -d --restart unless-stopped --memory=256m --network="host" "$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG"

echo "✅ Docker containers deployed!"
