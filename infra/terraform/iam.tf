# Two roles, and the difference matters more than it looks.
#
#   EXECUTION role  assumed by the ECS agent BEFORE your containers start.
#                   Pulls the image, creates log streams, and resolves the
#                   `secrets` block — which is how cloudflared gets its token,
#                   since it is Cloudflare's image and has no entrypoint of ours.
#
#   TASK role       assumed by the running containers themselves. This is what
#                   wishly.bootstrap authenticates with to read wishly/prod.
#
# Getting the secret permission onto only one of them fails in a confusing way:
# missing on the execution role, the task never starts and the reason appears in
# the task's stopped reason rather than in any container log, because nothing
# ran to log it.

data "aws_caller_identity" "current" {}

# The one secret, addressed by prefix. Secrets Manager appends six random
# characters to every ARN, so `...:secret:wishly/prod` matches nothing.
locals {
  secret_arn_pattern = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:wishly/prod-*"
}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "read_secret" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [local.secret_arn_pattern]
  }
}

# --- Execution role -------------------------------------------------------
resource "aws_iam_role" "execution" {
  name               = "wishly-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

# CloudWatch Logs (and ECR pull, unused now that the image is on GHCR). AWS maintains this one; there is no value in
# hand-writing the same statements and then keeping them current.
resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Only so the agent can inject TUNNEL_TOKEN into the cloudflared container.
resource "aws_iam_role_policy" "execution_secret" {
  name   = "read-wishly-prod"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.read_secret.json
}

# --- Task role ------------------------------------------------------------
resource "aws_iam_role" "task" {
  name               = "wishly-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

# Exactly one action on exactly one secret. The containers need nothing else in
# the account, and a role that can do nothing else cannot be used for anything
# else if a task is ever compromised.
resource "aws_iam_role_policy" "task_secret" {
  name   = "read-wishly-prod"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.read_secret.json
}
