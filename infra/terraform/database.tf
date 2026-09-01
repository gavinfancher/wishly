# RDS Postgres in the isolated subnets.
#
# Three resources, three different layers — none of them is "another database":
#
#   aws_subnet.private_a/b   address ranges (in network.tf)
#   aws_db_subnet_group      a LIST of subnets RDS may place the instance in
#   aws_db_instance          the actual Postgres server, one of them
#
# RDS picks a subnet from the group and puts the instance's network interface
# there. That ENI is what shows up in EC2 -> Network Interfaces as
# "RDSNetworkInterface", and its private IP is the address you'd resolve the
# endpoint hostname to.

# Not a network — pure metadata. Costs nothing, creates nothing.
#
# It contains ONLY the two isolated subnets, which is the structural fix for
# open item #2 in docs/runbooks/aws-vpc-tailscale.md: prod's group spans the
# public subnets too, so a restore could legitimately place the database in a
# publicly-routable subnet, or inside the 10.0.0.x range the home LAN shadows.
# With this group, that placement is not a rule to remember — it is unavailable.
resource "aws_db_subnet_group" "main" {
  name       = "wishly-tf-test"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = { Name = "wishly-tf-test" }
}

resource "aws_db_instance" "main" {
  identifier = "wishly-tf-test"

  engine = "postgres"
  # 18.4 matches the postgres image CLAUDE.md pins for local Docker. Prod runs
  # 18.3 — that drift is runbook open item #9, not something to reproduce here.
  engine_version = "18.4"
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  # The initial logical database inside the server. Distinct from the instance
  # identifier above: DATABASE_URL walks both — postgresql://…@<endpoint>/<db_name>.
  # Tables are still built by infra/sql/schema.sql; Terraform never manages those.
  db_name  = "wishly"
  username = "wishly"

  # Set from terraform.tfvars, which is gitignored. The two are mutually
  # exclusive: you cannot pass `password` and `manage_master_user_password`
  # together.
  #
  # Testing-only choice. `manage_master_user_password = true` is better for
  # anything real — RDS generates and rotates the credential in Secrets Manager
  # and Terraform never sees it, whereas this value IS written to
  # terraform.tfstate in plaintext.
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  availability_zone      = "us-east-1a" # same AZ as the VM: no cross-AZ transfer charges

  # THE setting to get right. `true` gives the instance a public endpoint even
  # though it sits in an isolated subnet — it does not move the database, it
  # adds an internet-routable address, and the subnet placement stops protecting
  # anything. Defaults to false; worth stating explicitly anyway.
  publicly_accessible = false

  # --- sandbox-only settings. All three are wrong for a real database. -------
  skip_final_snapshot     = true # `destroy` deletes it with no backup
  backup_retention_period = 0    # no automated backups at all
  deletion_protection     = false

  # For anything real, flip those and add:
  #   lifecycle { prevent_destroy = true }
  # which makes Terraform refuse the plan outright rather than trusting you to
  # read it.

  tags = { Name = "wishly-tf-test" }
}
