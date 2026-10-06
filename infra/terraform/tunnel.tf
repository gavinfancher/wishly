# Cloudflare Tunnel: the VM dials out to Cloudflare, so it needs no open ports
# and no public IP. https://api.<domain> → tunnel → cloudflared → the API.

locals {
  api_host = "${var.api_subdomain}.${var.domain}"
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "api" {
  account_id = var.cloudflare_account_id
  name       = "wishly-api"
  config_src = "cloudflare" # routes live here, not in a file on the VM
}

# The token cloudflared runs with. Output below, for you to put in Infisical.
data "cloudflare_zero_trust_tunnel_cloudflared_token" "api" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.api.id
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "api" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.api.id
  config = {
    ingress = [
      # cloudflared shares the API container's network, so the API is localhost.
      { hostname = local.api_host, service = "http://localhost:8000" },
      { service = "http_status:404" }, # anything else
    ]
  }
}

resource "cloudflare_dns_record" "api" {
  zone_id = var.cloudflare_zone_id
  name    = var.api_subdomain
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.api.id}.cfargotunnel.com"
  proxied = true
  ttl     = 1 # "automatic"; required for proxied records
}
