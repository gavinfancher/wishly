# Terraform and provider version constraints.
#
# Split out by convention so it is obvious where to look when a `terraform init`
# starts pulling something unexpected. Nothing here creates infrastructure.

terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0" # 6.x, but not 7.0 — allows patches, blocks breaking majors
    }
  }
}
