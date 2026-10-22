# --- AWS (cleanup only; remove with the providers in versions.tf) -------------

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

# --- Cloudflare --------------------------------------------------------------

variable "cloudflare_account_id" {
  type = string
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Zone ID of the domain the API is served under."
}

variable "domain" {
  type        = string
  description = "The domain that zone serves, e.g. wishly.dev."
}

variable "api_subdomain" {
  type    = string
  default = "api"
}

# --- The app -----------------------------------------------------------------

variable "frontend_origin" {
  type        = string
  description = "Where the frontend is served, e.g. https://wishly.dev. Allowed by CORS."
}
