output "api_url" {
  value = "https://${local.api_host}"
}

output "planetscale_database" {
  value = "${var.planetscale_org}/${var.database_name}"
}

# Everything the VM needs, for you to add to Infisical (prod) by hand. Hidden
# in plan/apply output; show it with:
#
#   terraform output -json infisical_values
#
# Also add WISHLY_RESEND_API_KEY yourself, from Resend's dashboard.
output "infisical_values" {
  sensitive = true
  value = {
    WISHLY_DATABASE_URL        = local.db_url.app
    WISHLY_SCHEMA_DATABASE_URL = local.db_url.schema
    WISHLY_RUN_TOKEN           = random_password.run_token.result
    TUNNEL_TOKEN               = data.cloudflare_zero_trust_tunnel_cloudflared_token.api.token
    WISHLY_CLERK_ISSUER        = var.clerk_issuer
    WISHLY_CORS_ORIGINS        = jsonencode([var.frontend_origin])
    WISHLY_IMAGE               = var.image
  }
}
