# --- AWS ---------------------------------------------------------------------

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

# --- PlanetScale -------------------------------------------------------------

variable "planetscale_org" {
  type        = string
  description = "Your PlanetScale organization name."
}

variable "database_name" {
  type    = string
  default = "wishly"
}

variable "planetscale_region" {
  type        = string
  description = "PlanetScale region slug. null = your organization's default."
  default     = null
}

variable "planetscale_cluster_size" {
  type        = string
  description = "PlanetScale cluster size, e.g. PS_10_AWS_ARM. null = PlanetScale's default."
  default     = null
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

variable "clerk_issuer" {
  type        = string
  description = "Clerk Frontend API URL, e.g. https://clerk.wishly.dev."
}

variable "frontend_origin" {
  type        = string
  description = "Where the frontend is served, e.g. https://wishly.dev. Allowed by CORS."
}

variable "image" {
  type        = string
  description = "The API image the VM runs."
  default     = "ghcr.io/gavinfancher/wishly:latest"
}
