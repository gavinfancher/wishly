output "ecr_registry" {
  description = "Registry host to docker login against. infra/images.sh derives this itself."
  value       = split("/", aws_ecr_repository.app["api"].repository_url)[0]
}

output "ecr_repositories" {
  description = "Repository URLs, by image name."
  value       = { for k, r in aws_ecr_repository.app : k => r.repository_url }
}

output "failover_up" {
  description = "Run this when home is gone."
  value       = "aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service ${aws_ecs_service.app.name} --desired-count 1 --region ${var.region}"
}

output "failover_down" {
  description = "Run this by hand once home is back. Never automate failback."
  value       = "aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service ${aws_ecs_service.app.name} --desired-count 0 --region ${var.region}"
}

output "logs" {
  description = "Tail the task."
  value       = "aws logs tail ${aws_cloudwatch_log_group.app.name} --follow --region ${var.region}"
}

output "github_ci_role_arn" {
  description = "Put this in .github/workflows/build.yml as role-to-assume."
  value       = aws_iam_role.github_ci.arn
}
