variable "region" {
  description = "Every Wishly resource lives here. Hardcoded in bootstrap.py too."
  type        = string
  default     = "us-east-1"
}

variable "image_tag" {
  description = "GHCR tag the failover task runs: latest, or a 7-char commit SHA to pin/roll back."
  type        = string
  default     = "latest"
}

variable "secrets_id" {
  description = "Secrets Manager secret holding the app environment (Infisical owns its contents)."
  type        = string
  default     = "wishly/prod"
}

variable "api_base_url" {
  description = "Public origin of the API, through the Cloudflare Tunnel. Probed and triggered."
  type        = string
  default     = "https://api.wishly.dev"
}

variable "trigger_token" {
  description = <<-EOT
    Shared secret for the X-Wishly-Trigger header on the API's /internal routes.
    Must equal TRIGGER_TOKEN in the Secrets Manager secret Infisical owns — the
    API compares them and nothing reconciles the two automatically.
  EOT
  type        = string
  sensitive   = true
}

variable "send_schedule_expression" {
  description = <<-EOT
    When the reminder send runs. cron, not rate(1 hour), on purpose: a rate
    expression ticks relative to when the rule was created, so delivery jitter
    can drift a tick across an hour boundary and leave one clock hour with two
    ticks and another with none. A skipped hour is a skipped reminder — the send
    window is `local hour == send_hour` and there is no second chance that day.
  EOT
  type        = string
  default     = "cron(0 * * * ? *)"
}

variable "send_enabled" {
  description = "False stops the hoursly sends without destroying the rule (see detector_enabled)."
  type        = bool
  default     = true
}

variable "detector_enabled" {
  description = "False stops the watchdog polling without destroying it (planned VM maintenance)."
  type        = bool
  default     = true
}
