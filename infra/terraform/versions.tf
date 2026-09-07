terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0" # patches yes, breaking majors no
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "wishly"
      ManagedBy = "terraform"
    }
  }
}
