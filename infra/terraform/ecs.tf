# The failover target: one task, two containers, normally not running.
#
# SIZING is measured, not guessed. At rest: api 89 MiB, prefect's import 80 MiB
# before any flow run, cloudflared ~40 MiB. 0.5 vCPU / 2 GB left room for the
# subprocess Prefect forked per flow run, which paid that 80 MiB again.
# On x86 Fargate that is $0.04048/vCPU-hr + $0.004445/GB-hr = $0.0291/hr.
#
# OVERPROVISIONED NOW, DELIBERATELY. The Prefect worker container is gone — the
# hourly send is an EventBridge rule POSTing to the api container — so both the
# 80 MiB import and the forked subprocess left with it, and 2 GB is roughly
# double what this needs. Resizing is part of the failover pass, not this
# change: it wants a measurement under a real run, not a guess minus a guess.

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
    # X86_64, not Graviton. The PVE VM is x86_64, and matching it means both
    # runtimes pull the same image digest instead of running two builds of the
    # same source. Graviton would save ~$0.11/month; parity is worth more.
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name = "api"
      # ECR, while CI now publishes to ghcr.io/gavinfancher/wishly. Nothing
      # reconciles the two: `terraform apply -var image_tag=<sha>` is accepted
      # whether or not that tag was ever pushed HERE, and because desired_count
      # is 0 nothing attempts the pull until a real failover — which then cannot
      # start. Run `infra/images.sh --push` for every tag you apply, or point
      # this at the (public) GHCR package and delete the ECR path entirely.
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
