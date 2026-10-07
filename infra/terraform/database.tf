# PlanetScale Postgres. Creating the branch creates the database around it.

resource "planetscale_postgres_branch" "main" {
  organization  = var.planetscale_org
  database      = var.database_name
  name          = "main"
  region        = var.planetscale_region
  cluster_size  = var.planetscale_cluster_size
  major_version = "18"

  # Destroying this deletes the database and every row in it. Terraform will
  # refuse to; to really tear everything down, delete this block first.
  lifecycle {
    prevent_destroy = true
  }
}

# Two roles, least privilege:
#   wishly_app     — what the API connects as. Reads and writes rows; can't
#                    create, alter or drop tables.
#   wishly_schema  — only for applying infra/sql/schema.sql by hand.

resource "planetscale_postgres_branch_role" "app" {
  organization    = var.planetscale_org
  database        = var.database_name
  branch          = planetscale_postgres_branch.main.id
  name            = "wishly_app"
  inherited_roles = ["pg_read_all_data", "pg_write_all_data"]
}

resource "planetscale_postgres_branch_role" "schema" {
  organization    = var.planetscale_org
  database        = var.database_name
  branch          = planetscale_postgres_branch.main.id
  name            = "wishly_schema"
  inherited_roles = ["postgres"]
}

locals {
  # verify-full: check PlanetScale's certificate and hostname, so the connection
  # can't be silently intercepted. The CA file is named explicitly rather than
  # `sslrootcert=system`: psycopg-binary ships its own OpenSSL, which doesn't know
  # where Debian keeps CAs, so `system` fails in the API image. This path is the
  # Debian CA bundle, present in the python:slim image the API runs on.
  db_url = {
    for key, role in {
      app    = planetscale_postgres_branch_role.app
      schema = planetscale_postgres_branch_role.schema
    } :
    key => format(
      "postgresql://%s:%s@%s:5432/%s?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt",
      role.username, urlencode(role.password), role.access_host_url, role.database_name,
    )
  }
}
