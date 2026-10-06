# The hourly trigger: EventBridge calls POST https://api.<domain>/internal/run
# at minute 0 of every hour, with the run token as a Bearer token.

resource "random_password" "run_token" {
  length  = 48
  special = false
}

# Holds the credential EventBridge sends. AWS keeps it in Secrets Manager.
resource "aws_cloudwatch_event_connection" "api" {
  name               = "wishly-api"
  authorization_type = "API_KEY"
  auth_parameters {
    api_key {
      key   = "Authorization"
      value = "Bearer ${random_password.run_token.result}"
    }
  }
}

resource "aws_cloudwatch_event_api_destination" "run" {
  name                             = "wishly-run"
  invocation_endpoint              = "https://${local.api_host}/internal/run"
  http_method                      = "POST"
  connection_arn                   = aws_cloudwatch_event_connection.api.arn
  invocation_rate_limit_per_second = 1
}

resource "aws_cloudwatch_event_rule" "hourly" {
  name                = "wishly-hourly-run"
  schedule_expression = "cron(0 * * * ? *)"
}

resource "aws_cloudwatch_event_target" "run" {
  rule     = aws_cloudwatch_event_rule.hourly.name
  arn      = aws_cloudwatch_event_api_destination.run.arn
  role_arn = aws_iam_role.eventbridge.arn

  # Retrying is safe: the API's `sends` table stops duplicate emails. Give up
  # after 10 minutes, well inside the one-hour sending window.
  retry_policy {
    maximum_retry_attempts       = 3
    maximum_event_age_in_seconds = 600
  }
}

# EventBridge needs permission to call the API destination, and nothing else.
resource "aws_iam_role" "eventbridge" {
  name = "wishly-eventbridge"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge" {
  name = "invoke-wishly-run"
  role = aws_iam_role.eventbridge.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "events:InvokeApiDestination"
      Resource = aws_cloudwatch_event_api_destination.run.arn
    }]
  })
}
