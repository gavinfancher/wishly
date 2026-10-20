# The watchdog. EventBridge invokes a small Lambda every minute; the Lambda
# calls GET https://api.<domain>/internal/ping with the ping key, and pushes a
# notification through ntfy once Wishly has been down for alert_after_minutes
# (and again when it recovers). Code: lambda/watchdog.py.
#
# This is the only thing Wishly runs on AWS. The daily send happens inside the
# app itself.

resource "random_password" "ping_token" {
  length  = 48
  special = false
}

data "archive_file" "watchdog" {
  type        = "zip"
  source_file = "${path.module}/lambda/watchdog.py"
  output_path = "${path.module}/.build/watchdog.zip"
}

# Created here rather than by Lambda on first run, so it has a retention
# period and Terraform deletes it on destroy instead of leaving it behind.
resource "aws_cloudwatch_log_group" "watchdog" {
  name              = "/aws/lambda/wishly-watchdog"
  retention_in_days = 14
}

# One item: when Wishly was first seen down, and whether we've alerted. Lambda
# invocations share nothing else, so "down for 5 minutes" has to live here.
# On-demand billing: ~2 small writes per outage, one read a minute.
resource "aws_dynamodb_table" "watchdog" {
  name         = "wishly-watchdog"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

resource "aws_lambda_function" "watchdog" {
  function_name    = "wishly-watchdog"
  role             = aws_iam_role.watchdog.arn
  runtime          = "python3.14"
  architectures    = ["arm64"]
  handler          = "watchdog.handler"
  filename         = data.archive_file.watchdog.output_path
  source_code_hash = data.archive_file.watchdog.output_base64sha256
  timeout          = 30 # the ping itself gives up after 10s
  memory_size      = 128

  environment {
    variables = {
      PING_URL            = "https://${local.api_host}/internal/ping"
      PING_TOKEN          = random_password.ping_token.result
      NTFY_URL            = var.ntfy_topic == "" ? "" : "https://ntfy.sh/${var.ntfy_topic}"
      STATE_TABLE         = aws_dynamodb_table.watchdog.name
      ALERT_AFTER_SECONDS = tostring(var.alert_after_minutes * 60)
    }
  }

  depends_on = [aws_cloudwatch_log_group.watchdog]
}

# No retries: the next check is a minute away anyway, and a retry landing late
# would only muddle the timeline.
resource "aws_lambda_function_event_invoke_config" "watchdog" {
  function_name                = aws_lambda_function.watchdog.function_name
  maximum_retry_attempts       = 0
  maximum_event_age_in_seconds = 60
}

resource "aws_cloudwatch_event_rule" "every_minute" {
  name                = "wishly-watchdog"
  schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "watchdog" {
  rule = aws_cloudwatch_event_rule.every_minute.name
  arn  = aws_lambda_function.watchdog.arn
}

# Lets this one EventBridge rule, and nothing else, invoke the function.
resource "aws_lambda_permission" "watchdog" {
  statement_id  = "AllowEveryMinuteRule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.watchdog.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_minute.arn
}

# The function may write to its own log group and read/write its own state
# item, nothing else.
resource "aws_iam_role" "watchdog" {
  name = "wishly-watchdog"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "watchdog" {
  name = "logs-and-state"
  role = aws_iam_role.watchdog.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.watchdog.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem"]
        Resource = aws_dynamodb_table.watchdog.arn
      },
    ]
  })
}
