terraform {
  required_version = ">= 1.11"

  # Where state lives. Values come from backend.hcl, so anyone can point this
  # at their own bucket:  terraform init -backend-config=backend.hcl
  backend "s3" {}

  required_providers {
    aws         = { source = "hashicorp/aws", version = "~> 6.0" }
    cloudflare  = { source = "cloudflare/cloudflare", version = "~> 5.8" }
    planetscale = { source = "planetscale/planetscale", version = "~> 1.3" }
    random      = { source = "hashicorp/random", version = "~> 3.6" }
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

provider "cloudflare" {}  # CLOUDFLARE_API_TOKEN
provider "planetscale" {} # PLANETSCALE_SERVICE_TOKEN_ID, PLANETSCALE_SERVICE_TOKEN
