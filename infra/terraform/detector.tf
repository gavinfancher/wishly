# The failover trigger: a Lambda on a one-minute schedule, its counter in
# DynamoDB, scaling the ECS service up when the app host stops being seen.

resource "aws_dynamodb_table" "detector" {
  name         = "wishly-failover-state"
  billing_mode = "PAY_PER_REQUEST" # ~43k writes/month; nothing to provision
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# --- IAM ------------------------------------------------------------------
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "detector" {
  name               = "wishly-detector"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "detector_logs" {
  role       = aws_iam_role.detector.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "detector" {
  statement {
    sid       = "ReadConfig"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [local.secret_arn_pattern]
  }
  statement {
    sid       = "Counter"
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.detector.arn]
  }
  statement {
    sid = "ScaleUpOnly"
    # UpdateService on ONE service. It cannot touch the task definition, cannot
    # create or delete anything, and cannot reach any other service in the
    # cluster. A watchdog should be able to do exactly the one thing it exists
    # for.
    actions   = ["ecs:UpdateService"]
    resources = [aws_ecs_service.app.id]
  }
}

resource "aws_iam_role_policy" "detector" {
  name   = "detector"
  role   = aws_iam_role.detector.id
  policy = data.aws_iam_policy_document.detector.json
}

# --- Function -------------------------------------------------------------
resource "aws_lambda_function" "detector" {
  function_name = "wishly-detector"
  role          = aws_iam_role.detector.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  architectures = ["arm64"] # matches the wheels build.sh resolves
  timeout       = 30
  memory_size   = 256

  filename         = "${path.module}/../lambda/detector.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambda/detector.zip")

  environment {
    variables = {
      STATE_TABLE          = aws_dynamodb_table.detector.name
      TAILSCALE_DEVICE_ID  = var.tailscale_device_id
      ECS_CLUSTER          = aws_ecs_cluster.main.name
      ECS_SERVICE          = aws_ecs_service.app.name
      WISHLY_SECRETS_ID    = var.secrets_id
      FRESH_WITHIN_SECONDS = "60"
      THRESHOLD            = "3"
    }
  }
}

resource "aws_cloudwatch_log_group" "detector" {
  name              = "/aws/lambda/${aws_lambda_function.detector.function_name}"
  retention_in_days = 14
}

# --- Schedule -------------------------------------------------------------
# Detection latency is INTERVAL x THRESHOLD plus however long Tailscale's
# control plane takes to stop refreshing lastSeen — about three minutes at these
# settings, before ECS even starts pulling images.
resource "aws_cloudwatch_event_rule" "detector" {
  name                = "wishly-detector"
  description         = "Poll the Tailscale device every minute"
  schedule_expression = "rate(1 minute)"
  # Disable this to stop the watchdog without deleting anything — the switch to
  # flip during planned VM maintenance so it does not fail over on you.
  state = var.detector_enabled ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "detector" {
  rule = aws_cloudwatch_event_rule.detector.name
  arn  = aws_lambda_function.detector.arn
}

resource "aws_lambda_permission" "detector" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.detector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.detector.arn
}
