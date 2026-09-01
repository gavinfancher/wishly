# Security groups — the stateful, per-instance firewall.
#
# Separate from network.tf because this is the file that grows fastest: every
# new port, service, or peer lands here, and it is the one you want to read in
# isolation during a review.

resource "aws_security_group" "vm" {
  name        = "wishly-tf-test"
  description = "SSH in, everything out"
  vpc_id      = aws_vpc.main.id

  # Inline rules are the simple form. The tradeoff: Terraform treats this list
  # as the whole truth, so a rule added by hand in the console gets reverted on
  # the next apply. Fine while Terraform is the only thing touching it.
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # No default egress exists on a Terraform-managed SG — omit this and the box
  # cannot reach apt, and cloud-init hangs.
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "wishly-tf-test" }
}

# Database firewall: Postgres, reachable only from the VM.
#
# Note `security_groups` rather than `cidr_blocks`. A subnet router SNATs the
# traffic it forwards, so by the time a packet from your laptop reaches the
# database it appears to come from the router's own network interface — the
# tailnet address is long gone. A rule written against 100.64.0.0/10 would
# match nothing at all, and fail as a bare timeout with no diagnostic.
resource "aws_security_group" "db" {
  name        = "wishly-tf-test-db"
  description = "Postgres from the VM only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from the VM"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.vm.id]
  }

  # No egress rule. The database has no reason to originate connections, and
  # its subnet has no route to the internet anyway.

  tags = { Name = "wishly-tf-test-db" }
}
