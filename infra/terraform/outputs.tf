output "ecr_registry" {
  description = "Registry host to docker login against. infra/images.sh derives this itself."
  value       = split("/", aws_ecr_repository.app["api"].repository_url)[0]
}

output "ecr_repositories" {
  description = "Repository URLs, by image name."
  value       = { for k, r in aws_ecr_repository.app : k => r.repository_url }
}
