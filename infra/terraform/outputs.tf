output "api_url" {
  value = "https://${local.api_host}"
}

# The Terraform-made half of the cluster's `wishly` Secret. Hidden in
# plan/apply output; copy it into Infisical (prod, /wishly) from:
#
#   terraform output -json cluster_secret_values
#
# The other half you add there yourself: WISHLY_RESEND_API_KEY (Resend's
# dashboard) and WISHLY_DATABASE_URL (the wishly_app role; see infra/sql/roles.sql).
output "cluster_secret_values" {
  sensitive = true
  value = {
    WISHLY_PING_TOKEN   = random_password.ping_token.result
    TUNNEL_TOKEN        = data.cloudflare_zero_trust_tunnel_cloudflared_token.api.token
    WISHLY_CORS_ORIGINS = jsonencode([var.frontend_origin])
  }
}
