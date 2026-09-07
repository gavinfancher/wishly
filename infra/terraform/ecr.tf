# Where the images live so ECS can pull them.
#
# Two repositories, one per image. Fargate re-pulls on every cold start, so
# these sit in the same region as the tasks — a cross-region pull would be paid
# for in recovery time.

locals {
  images = toset(["api", "worker"])
}

resource "aws_ecr_repository" "app" {
  for_each = local.images
  name     = "wishly-${each.key}"

  # A tag can never be repointed at different bytes. `:latest` moving under you
  # is the usual way "it works locally" stops meaning anything, and it makes a
  # rollback ambiguous: the tag a task definition names must be one image
  # forever.
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Untagged layers accumulate every time a tag is superseded. Nothing can pull
# them and nobody looks at them, so they are pure storage.
resource "aws_ecr_lifecycle_policy" "expire_untagged" {
  for_each   = aws_ecr_repository.app
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "expire untagged images after 7 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 7
      }
      action = { type = "expire" }
    }]
  })
}
