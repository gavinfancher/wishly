# The instance, and the AMI lookup that feeds it.

# Canonical publishes the current Ubuntu 26.04 arm64 image id here, so we get a
# live value instead of a hardcoded ami-* that goes stale. A `data` block reads
# something that already exists; it never creates or changes anything.
data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/26.04/stable/current/arm64/hvm/ebs-gp3/ami-id"
}

resource "aws_instance" "vm" {
  ami           = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type = "t4g.micro" # arm64, 1 GiB, ~$6/mo
  key_name      = "macbook-pro-key"

  # These live in network.tf and security.tf. Terraform does not care which file
  # a resource is declared in — it reads every .tf in this directory as one
  # config and builds the ordering from references like these.
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.vm.id]

  # EC2 drops any packet whose source or destination is not this instance —
  # which is every packet a subnet router forwards. Leave this at its default
  # of true and Tailscale reports healthy, the route shows approved, and no
  # traffic reaches the VPC. Changing it is an in-place update, not a rebuild.
  source_dest_check = false

  # file() reads the file as-is. Its sibling templatefile() would substitute
  # ${...} placeholders — not needed here, since nothing in the file varies.
  user_data = file("${path.module}/cloud-init.yaml")

  # Cloud-init only runs on FIRST boot. Without this, editing cloud-init.yaml
  # and applying would stop/start the instance and change nothing — Terraform
  # would report success and the box would be untouched. This rebuilds it
  # instead, so what the file says is what the box has.
  user_data_replace_on_change = true

  tags = { Name = "wishly-tf-test" }
}
