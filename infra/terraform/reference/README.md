# Reference configs

Working Terraform kept for reference, **not** applied by the module in the parent
directory. `terraform` never reads a subdirectory, so nothing here is part of a
plan — it is here to be read and copied from.

| File | What it is |
| --- | --- |
| `main.tf.full` | The Tailscale subnet router, as one self-contained parameterised module: security group, EC2, EIP, and the cloud-init below. |
| `cloud-init.yaml` | The router's full first-boot config — the masked memory hogs, the swapfile, IP forwarding, the GRO tuning hook, and `tailscale up --advertise-routes`. Rendered through `templatefile()`, so `$${...}` in it is Terraform interpolation, not shell. |

## How this relates to `../*.tf`

They are different stacks, not two versions of one.

- **`../*.tf`** is the `wishly-tf-test` sandbox: a VPC, one EC2, and an RDS
  instance, split across `network.tf` / `compute.tf` / `security.tf` /
  `database.tf` to learn how Terraform composes a config from a directory. Its
  `cloud-init.yaml` is deliberately cut down to the bare minimum.
- **`main.tf.full`** is the production-shaped article, written as a single file
  with `variable` blocks so it could be consumed as a module.

Read the sandbox to see the structure; read this to see what the real thing has
to do.
