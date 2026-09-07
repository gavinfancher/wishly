# The failover target: one task, three containers, normally not running.
#
# SIZING is measured, not guessed. At rest: api 89 MiB, prefect's import 80 MiB
# before any flow run, cloudflared ~40 MiB. 0.5 vCPU / 2 GB leaves room for the
# subprocess Prefect forks per flow run, which pays that 80 MiB again.
#
# ONE TASK rather than two services: at this size nothing wants to scale the API
# independently of the worker, and a single task means the failover action is
# one API call instead of two that can disagree.

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/wishly"
  retention_in_days = 14
}

resource "aws_ecs_cluster" "main" {
  name = "wishly"

  setting {
    name  = "containerInsights"
    value = "disabled" # billed per metric; the log group is enough here
  }
}

locals {
  registry = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"

  # Shared by both application containers: same image config path as compose.
  app_env = [
    { name = "WISHLY_SECRETS_ID", value = var.secrets_id },
  ]

  log_config = {
    logDriver = "awslogs"
    options = {
      "awslogs-group"         = aws_cloudwatch_log_group.app.name
      "awslogs-region"        = var.region
      "awslogs-stream-prefix" = "wishly"
    }
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = "wishly"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"  # 0.5 vCPU
  memory                   = "2048" # 2 GB
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    cpu_architecture        = "ARM64" # Graviton: cheaper, and what images.sh builds
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name             = "api"
      image            = "${local.registry}/wishly-api:${var.image_tag}"
      essential        = true
      environment      = local.app_env
      portMappings     = [{ containerPort = 8000, protocol = "tcp" }]
      logConfiguration = local.log_config
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request;urllib.request.urlopen('http://localhost:8000/health')\""]
        interval    = 15
        timeout     = 5
        retries     = 5
        startPeriod = 30
      }
    },
    {
      name  = "worker"
      image = "${local.registry}/wishly-worker:${var.image_tag}"
      # NOT essential: the send pipeline dying should not take the API and the
      # tunnel down with it. ECS restarts the container; the task survives.
      essential        = false
      environment      = local.app_env
      logConfiguration = local.log_config
    },
    {
      name      = "cloudflared"
      image     = "cloudflare/cloudflared:2026.8.3"
      essential = true
      command   = ["tunnel", "--no-autoupdate", "--metrics", "0.0.0.0:2000", "run"]

      # The ECS agent resolves this from Secrets Manager using the EXECUTION
      # role. cloudflared is Cloudflare's image, so it has no entrypoint of ours
      # to load config — this is the one value injected rather than fetched.
      secrets = [
        {
          name      = "TUNNEL_TOKEN"
          valueFrom = "${data.aws_secretsmanager_secret.app.arn}:TUNNEL_TOKEN::"
        }
      ]

      # No extraHosts: awsvpc forbids them. Not needed either — every container
      # in the task shares one network namespace, so the API is on localhost.
      # infra/compose.yaml gives cloudflared `network_mode: service:api` so the
      # same http://localhost:8000 route works there too, which is why the
      # Cloudflare dashboard needs exactly one hostname entry for both.

      dependsOn        = [{ containerName = "api", condition = "HEALTHY" }]
      logConfiguration = local.log_config
    },
  ])
}

# The secret already exists — Infisical creates and owns its contents. Terraform
# only needs its ARN, and must not manage it.
data "aws_secretsmanager_secret" "app" {
  name = var.secrets_id
}

resource "aws_ecs_service" "app" {
  name            = "wishly"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  launch_type     = "FARGATE"

  # Zero. This exists to be scaled to 1 when home is gone, and costs nothing
  # until it is. Failing over is:
  #   aws ecs update-service --cluster wishly --service wishly --desired-count 1
  desired_count = 0

  network_configuration {
    subnets         = [for s in aws_subnet.public : s.id]
    security_groups = [aws_security_group.tasks.id]
    # Required in a public subnet with no NAT: without a public IP the task
    # cannot reach ECR to pull its own image, and fails before it starts.
    assign_public_ip = true
  }

  # Terraform sets the count only at creation. After that it is an operational
  # value — a failover raises it, and a plan must never quietly put it back to
  # zero while you are relying on it.
  lifecycle {
    ignore_changes = [desired_count]
  }
}
