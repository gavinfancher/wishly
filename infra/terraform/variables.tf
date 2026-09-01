# Inputs. Values come from terraform.tfvars (gitignored), TF_VAR_* environment
# variables, or an HCP workspace variable — never from a file in this repo.

variable "db_password" {
  description = <<-EOT
    RDS master password.

    No default on purpose: Terraform prompts rather than silently falling back
    to something weak. `sensitive` keeps it out of plan/apply output — it does
    NOT keep it out of terraform.tfstate, which stores every attribute in
    plaintext. Treat the state file as a credential file.
  EOT
  type        = string
  sensitive   = true
}
