# GitHub Actions authenticates to AWS with no stored credentials.
#
# The build runner lives on Proxmox, not EC2, so it cannot carry an instance
# role. The usual fallback is a long-lived IAM user key parked on the build host
# forever — the same pattern that put static keys in infra/.env. OIDC removes
# it: GitHub mints a short-lived token for each workflow run, STS trades that
# for credentials which expire in an hour, and nothing is ever stored.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # No thumbprint_list. AWS validates this issuer against its own trusted CA
  # store, and a pinned thumbprint is one more thing that expires silently at
  # the worst moment.
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Scoped to one branch of one repository. WITHOUT this condition the role
    # would trust a workflow in ANY repository on GitHub — the single most
    # common way an OIDC role is misconfigured into a public back door.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_ci" {
  name               = "wishly-ci"
  description        = "Pushes images to ECR from GitHub Actions. No console, no keys."
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
}

data "aws_iam_policy_document" "ecr_push" {
  # GetAuthorizationToken takes no resource — it only mints a docker login for
  # repositories the caller can already reach through the statement below.
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Push, and read back enough to verify. Deliberately no ecr:DeleteImage and no
  # ecr:PutLifecyclePolicy: CI publishes, it never removes.
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [for r in aws_ecr_repository.app : r.arn]
  }
}

resource "aws_iam_role_policy" "github_ci_ecr" {
  name   = "ecr-push"
  role   = aws_iam_role.github_ci.id
  policy = data.aws_iam_policy_document.ecr_push.json
}
