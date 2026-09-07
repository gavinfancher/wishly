variable "region" {
  description = "Every Wishly resource lives here. Hardcoded in bootstrap.py too."
  type        = string
  default     = "us-east-1"
}

variable "image_tag" {
  description = "Commit SHA to run, as pushed by infra/images.sh."
  type        = string
}

variable "secrets_id" {
  description = "Secrets Manager secret holding the app environment (Infisical owns its contents)."
  type        = string
  default     = "wishly/prod"
}
