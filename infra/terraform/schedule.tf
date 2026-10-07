# The hourly trigger. EventBridge invokes a small Lambda at minute 0 of every
# hour; the Lambda calls POST https://api.<domain>/internal/run, logs the result
# to CloudWatch, and notifies your phone through ntfy. Code: lambda/hourly_run.py.

resource "random_password" "run_token" {
  length  = 48
  special = false
}

data "archive_file" "hourly_run" {
  type        = "zip"
  source_file = "${path.module}/lambda/hourly_run.py"
  output_path = "${path.module}/.build/hourly_run.zip"
}

# Created here rather than by Lambda on first run, so it has a retention
# period and Terraform deletes it on destroy instead of leaving it behind.
resource "aws_cloudwatch_log_group" "hourly_run" {
  name              = "/aws/lambda/wishly-hourly-run"
  retention_in_days = 30
}

resource "aws_lambda_function" "hourly_run" {
  function_name    = "wishly-hourly-run"
  role             = aws_iam_role.hourly_run.arn
  runtime          = "python3.14"
  architectures    = ["arm64"]
  handler          = "hourly_run.handler"
  filename         = data.archive_file.hourly_run.output_path
  source_code_hash = data.archive_file.hourly_run.output_base64sha256
  timeout          = 60 # the API call itself gives up after 50s
  memory_size      = 128

  environment {
    variables = {
      RUN_URL   = "https://${local.api_host}/internal/run"
      RUN_TOKEN = random_password.run_token.result
      NTFY_URL  = var.ntfy_topic == "" ? "" : "https://ntfy.sh/${var.ntfy_topic}"
    }
  }

  depends_on = [aws_cloudwatch_log_group.hourly_run]
}

# If the run fails, Lambda retries it. Safe: the API's `sends` table means a
# retried run never emails anyone twice. Give up after 10 minutes, well inside
# the one-hour sending window.
resource "aws_lambda_function_event_invoke_config" "hourly_run" {
  function_name                = aws_lambda_function.hourly_run.function_name
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 600
}

resource "aws_cloudwatch_event_rule" "hourly" {
  name                = "wishly-hourly-run"
  schedule_expression = "cron(0 * * * ? *)"
}

resource "aws_cloudwatch_event_target" "hourly_run" {
  rule = aws_cloudwatch_event_rule.hourly.name
  arn  = aws_lambda_function.hourly_run.arn
}

# Lets this one EventBridge rule, and nothing else, invoke the function.
resource "aws_lambda_permission" "hourly_run" {
  statement_id  = "AllowHourlyRule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.hourly_run.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.hourly.arn
}

# The function may write to its own log group, and nothing else.
resource "aws_iam_role" "hourly_run" {
  name = "wishly-hourly-run"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "hourly_run" {
  name = "write-own-logs"
  role = aws_iam_role.hourly_run.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "${aws_cloudwatch_log_group.hourly_run.arn}:*"
    }]
  })
}
