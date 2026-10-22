terraform {
  required_version = ">= 1.11"

  # Where state lives. Values come from backend.hcl, so anyone can point this
  # at their own bucket:  terraform init -backend-config=backend.hcl
  backend "s3" {}

  required_providers {
    cloudflare = { source = "cloudflare/cloudflare", version = "~> 5.8" }
    # TEMPORARY. Terraform manages only Cloudflare now, but state still holds
    # old AWS resources (the v2 Lambda and friends) and random passwords.
    # Destroying them needs these providers. After one `terraform apply` has
    # deleted them, remove these three, the aws provider block and aws_region,
    # then run `terraform init -upgrade`.
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
    archive = { source = "hashicorp/archive", version = "~> 2.7" }
  }
}

# Every provider reads its credentials from environment variables, so no
# secret is ever written in this directory. See ../../README.md for the list.

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "wishly", ManagedBy = "terraform" }
  }
}

provider "cloudflare" {} # CLOUDFLARE_API_TOKEN
