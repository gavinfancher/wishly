# The network the failover tasks run in.
#
# PUBLIC SUBNETS, DELIBERATELY. Fargate needs outbound internet to reach
# PlanetScale, Resend, Clerk and Cloudflare's edge. From a
# private subnet that means a NAT gateway at roughly $32/month — billed while
# idle, which is exactly what a scale-to-zero design exists to avoid. It would
# cost more per month than every failover this service will ever run.
#
# A public subnet with no inbound rules is not less safe here: nothing needs to
# reach these tasks. Inbound arrives through the Cloudflare tunnel, which is an
# outbound connection the task makes itself.
#
# 10.4.0.0/16 rather than 10.0.0.0/16: the home LAN uses 10.0.0.x, and an
# overlapping range breaks Tailscale subnet routing in ways that look like
# random connectivity loss.

resource "aws_vpc" "main" {
  cidr_block           = "10.4.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "wishly" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "wishly" }
}

# Two AZs. Fargate needs one, but if a single AZ has no capacity the task simply
# does not place — and discovering that during a failover is discovering it at
# the worst possible time. Subnets cost nothing.
resource "aws_subnet" "public" {
  for_each = {
    a = { cidr = "10.4.1.0/24", az = "${var.region}a" }
    b = { cidr = "10.4.2.0/24", az = "${var.region}b" }
  }

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = { Name = "wishly-public-${each.key}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "wishly-public" }
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# No ingress rules at all. The tunnel is an outbound connection the task opens
# to Cloudflare, so nothing ever needs to connect inward — and a security group
# with no ingress denies by default, which is stronger than any rule I could
# write and cannot drift.
resource "aws_security_group" "tasks" {
  name        = "wishly-tasks"
  description = "Wishly Fargate tasks: outbound only"
  vpc_id      = aws_vpc.main.id

  egress {
    description = "All outbound: PlanetScale, Resend, Clerk, Cloudflare"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "wishly-tasks" }
}
