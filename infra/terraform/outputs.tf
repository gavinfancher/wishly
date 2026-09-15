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
