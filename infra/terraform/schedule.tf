# The hourly send trigger: EventBridge -> HTTPS -> the API's /internal endpoint.
#
# This replaced Prefect Cloud. The schedule now lives in the same account and the
# same terraform as the failover it has to survive, rather than in a SaaS control
# plane that the whole point of the ECS standby is to not depend on.
#
# WHY THIS REACHES THE APP AT ALL. The target is api.wishly.dev, which Cloudflare
# routes down whichever cloudflared is connected to the tunnel — the Proxmox VM
# normally, the ECS task after a failover. So the schedule needs no idea where
# the app is running and nothing about it changes when that moves. Sending the
# same tick to both would also be harmless: `notification_log`'s
# insert-on-conflict claim means the second one sends nothing.
#
# AND WHY IT IS SAFE TO BE AT-LEAST-ONCE. EventBridge does not promise exactly
# one delivery. The claim protocol in wishly.orchestration.tasks is what makes
# that a non-issue, which is the same property that lets the API answer 202 and
# do the work afterwards.

# --- Connection: how EventBridge authenticates itself ------------------------
# API_KEY is EventBridge's name for "send this header". The value is stored in a
# Secrets Manager secret that EventBridge creates and owns through its
# service-linked role — it is not readable from here afterwards, which is why
# terraform.tfvars is the source of truth for it and not the other way round.
resource "aws_cloudwatch_event_connection" "wishly_api" {
  name               = "wishly-api"
  description        = "Shared-secret header for the Wishly API's /internal routes"
  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      # Must match TRIGGER_HEADER in wishly.api.routes.internal.
      key   = "X-Wishly-Trigger"
      value = var.trigger_token
    }
  }
}

# --- Destination: the endpoint itself ----------------------------------------
resource "aws_cloudwatch_event_api_destination" "send_reminders" {
  name        = "wishly-send-reminders"
  description = "Hourly reminder send"
  # Fire-and-forget: the route starts a background task and answers 202. It has
  # to — EventBridge times an API destination out after 5 seconds and a single
  # Resend call is allowed 30.
  invocation_endpoint = "${var.api_base_url}/internal/runs/send-reminders"
  http_method         = "POST"
  connection_arn      = aws_cloudwatch_event_connection.wishly_api.arn

  # One per second is already far more than one per hour. This is a ceiling
  # against a misconfiguration, not a tuning knob.
  invocation_rate_limit_per_second = 1
}

# --- Schedule ----------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "send_reminders" {
  name                = "wishly-send-reminders"
  description         = "Hourly tick for the reminder send pipeline"
  schedule_expression = var.send_schedule_expression

  # Same switch as detector_enabled: stop the sends without destroying the
  # wiring. Useful while testing a change you do not want emailing real people.
  state = var.send_enabled ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "send_reminders" {
  rule     = aws_cloudwatch_event_rule.send_reminders.name
  arn      = aws_cloudwatch_event_api_destination.send_reminders.arn
  role_arn = aws_iam_role.eventbridge_invoke.arn

  # The endpoint takes no parameters — what is due is a function of the clock and
  # the database, not of the event. An empty object rather than the default
  # EventBridge envelope keeps it that way, so nothing in the request can ever
  # become load-bearing.
  input = jsonencode({})

  # The API answers 202 before it does the work, so a retry here only ever
  # follows a genuine delivery failure (the tunnel down, the API not up). Two
  # attempts inside the hour, then stop: a third would land closer to the next
  # tick than to this one.
  retry_policy {
    maximum_retry_attempts       = 2
    maximum_event_age_in_seconds = 900
  }
}

# --- IAM: permission to invoke exactly this one destination ------------------
data "aws_iam_policy_document" "eventbridge_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "eventbridge_invoke" {
  statement {
    sid     = "InvokeSendReminders"
    actions = ["events:InvokeApiDestination"]
    # Scoped to the one destination. A role that can invoke any API destination
    # in the account is a role that can POST to anywhere one has been defined.
    resources = [aws_cloudwatch_event_api_destination.send_reminders.arn]
  }
}

resource "aws_iam_role" "eventbridge_invoke" {
  name               = "wishly-eventbridge-invoke"
  assume_role_policy = data.aws_iam_policy_document.eventbridge_assume.json
}

resource "aws_iam_role_policy" "eventbridge_invoke" {
  name   = "invoke-api-destination"
  role   = aws_iam_role.eventbridge_invoke.id
  policy = data.aws_iam_policy_document.eventbridge_invoke.json
}
