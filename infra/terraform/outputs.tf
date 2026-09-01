# Values printed after apply, and readable later with `terraform output`.
# Collected in one file so there is a single place to see what this module
# hands back to whoever runs it.

output "public_ip" {
  description = "ssh ubuntu@<this>"
  value       = aws_instance.vm.public_ip
}

output "vpc_id" {
  description = "Id of the VPC everything here lives in."
  value       = aws_vpc.main.id
}

output "db_endpoint" {
  description = "Hostname:port for psql/pgcli. Always use this, never the IP — it changes on failover and maintenance."
  value       = aws_db_instance.main.endpoint
}

output "db_username" {
  description = "Master username. The password is in terraform.tfvars, which is gitignored."
  value       = aws_db_instance.main.username
}
