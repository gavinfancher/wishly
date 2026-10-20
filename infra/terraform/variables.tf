# --- AWS ---------------------------------------------------------------------

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

# --- Notifications ------------------------------------------------------------

variable "ntfy_topic" {
  type        = string
  description = "ntfy.sh topic for watchdog alerts on your phone. Empty = no alerts. Anyone who knows the name can read it, so use a long random one."
  default     = ""
  sensitive   = true
}

variable "alert_after_minutes" {
  type        = number
  description = "How long Wishly must be down before the watchdog notifies you."
  default     = 5
}

# --- The app -----------------------------------------------------------------

variable "frontend_origin" {
  type        = string
  description = "Where the frontend is served, e.g. https://wishly.dev. Allowed by CORS."
}
