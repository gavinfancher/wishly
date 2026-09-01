
resource "aws_vpc" "main" {
  cidr_block = "10.4.0.0/16"

  enable_dns_hostnames = true

  tags = { Name = "wishly-tf-test" }
}

# A VPC has no route off itself until you attach one of these.
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "wishly-tf-test" }
}

resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.4.1.0/24"
  availability_zone = "us-east-1a"

  # What "public subnet" actually means is this line plus the route below.
  # Set here so the instance does not need associate_public_ip_address.
  map_public_ip_on_launch = true

  tags = { Name = "wishly-tf-test-public" }
}

# "Anything not local, send to the internet gateway."
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "wishly-tf-test-public" }
}

# A route table does nothing until a subnet is attached to it. Skip this and
# the instance launches, gets a public IP, and is still unreachable.
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# Private (isolated) subnets — currently empty.
#
# TWO of them, in two different availability zones, because RDS refuses to
# launch into a DB subnet group that does not span at least two AZs. That is
# the usual reason a "private subnet" is really a pair.
#
# These are ISOLATED, not merely private: their route table below has no
# 0.0.0.0/0 entry at all. Nothing in here can reach the internet, and the
# internet has no path in. Anything placed here would be unreachable except
# from inside the VPC.
#
# The alternative is private-with-egress, which means a NAT gateway: ~$32/month
# in us-east-1 plus per-GB. Worth it when instances here need to `apt install`.
# Not worth it for a database, which is why prod has no NAT gateway either.
# ---------------------------------------------------------------------------

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.4.10.0/24"
  availability_zone = "us-east-1a"

  # The inverse of the public subnet. Anything launched here gets no public IP.
  map_public_ip_on_launch = false

  tags = { Name = "wishly-tf-test-private-a" }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.4.11.0/24"
  availability_zone = "us-east-1b"

  map_public_ip_on_launch = false

  tags = { Name = "wishly-tf-test-private-b" }
}

# Note what is NOT here: no `route` block. Every route table gets an implicit
# local route for the VPC CIDR, so these subnets can talk to the public subnet
# and to each other — and nowhere else. That absence is the security property.
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "wishly-tf-test-private" }
}

resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}
