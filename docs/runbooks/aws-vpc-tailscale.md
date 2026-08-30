# AWS VPC + Tailscale Subnet Router Runbook

Reach private AWS resources — starting with an RDS Postgres instance that has no public
endpoint — directly from a laptop, over Tailscale, without a bastion host, a NAT gateway, or a
publicly exposed database.

Built 2026-08-29/30. This is a **test** environment; see [Open items](#open-items) before
treating any of it as production.

---

## Architecture recap

```
  gavin-macbook-pro (100.80.99.58)
          │ WireGuard (Tailscale)
          ▼
  wishly-vpc-router  ── tailnet: 100.90.214.84
  (EC2 t4g.nano)     ── VPC:     10.0.11.59
          │ IP forwarding + SNAT
          ▼
  VPC 10.0.0.0/16
          │
          ▼
  database-1 (RDS Postgres) — 10.0.134.113, no public endpoint
```

The router is the only machine with a foot in both networks. It advertises `10.0.0.0/16` to the
tailnet, so every Tailscale device routes VPC addresses through it. Nothing in the VPC needs to
know Tailscale exists.

**Key idea:** RDS, ElastiCache, Lambda and other managed services can never get a Tailscale IP,
because you cannot install the daemon on them. A subnet router is how you reach things that
can't join the tailnet themselves.

---

## Inventory

### Network

| Resource | ID | Notes |
| --- | --- | --- |
| VPC | `vpc-082652e0a55804c01` | `10.0.0.0/16`, DNS support + hostnames enabled |
| Internet gateway | `igw-09f4a2fc49583b62e` | |
| S3 gateway endpoint | `vpce-09f246734a4dbfe34` | Only egress the private subnets have |
| NAT gateway | *none* | Private subnets have **no** outbound internet |

### Subnets

| Subnet | CIDR | AZ | Routing |
| --- | --- | --- | --- |
| `subnet-05a06e430010ed238` | `10.0.0.0/20` | us-east-1a | IGW — **public** (router lives here) |
| `subnet-07fcd5665171ed94d` | `10.0.16.0/20` | us-east-1b | IGW — **public** |
| `subnet-0674a3a89fcb213e4` | `10.0.128.0/20` | us-east-1a | S3 endpoint only — **isolated** (RDS here) |
| `subnet-0e03120f5e965cf9e` | `10.0.144.0/20` | us-east-1b | S3 endpoint only — **isolated** |

### Compute + database

| Resource | Value |
| --- | --- |
| EC2 instance | `i-0f190f34d742cfd91` — t4g.nano, arm64, Ubuntu 26.04 (resolute) |
| Private / public IP | `10.0.11.59` / `3.91.102.140` |
| Tailscale | 1.102.3, hostname `wishly-vpc-router`, tailnet `kudu-cliff.ts.net` |
| Tailnet addresses | `100.90.214.84`, `fd7a:115c:a1e0::352f:d655` |
| RDS instance | `database-1` — Postgres 18.3, db.t4g.micro, 20 GB gp2, encrypted |
| RDS endpoint | `wishly-db.<id>.<region>.rds.amazonaws.com:5432` |
| RDS private IP | `10.0.134.113` (subject to change — always use the hostname) |

### Security groups

| Group | Purpose | Rules |
| --- | --- | --- |
| `sg-0c1fe6ce553f9aeb3` (`launch-wizard-2`) | EC2 router | Inbound `tcp/22` from `0.0.0.0/0`; egress all |
| `sg-0358d6914bd8d3d7e` (`default`) | RDS | Inbound all from itself; **+ `tcp/5432` from `sg-0c1fe6ce553f9aeb3`** |

---

## Step 1 — Disable the EC2 source/destination check

```bash
aws ec2 modify-instance-attribute \
  --instance-id i-0f190f34d742cfd91 \
  --no-source-dest-check
```

EC2 drops any packet whose source or destination isn't the instance itself — which is every
packet a subnet router forwards. **Do this first.** Left enabled, everything else installs
cleanly, the node reports healthy, the route shows approved, and no traffic reaches the VPC.

Verify: `SourceDestCheck` should read `False`.

---

## Step 2 — Enable IP forwarding on the router

```bash
# /etc/sysctl.d/99-tailscale.conf
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
```

```bash
sudo sysctl -p /etc/sysctl.d/99-tailscale.conf
```

Written under `/etc/sysctl.d/` rather than set live so it survives reboots. Both address
families, because the node holds a v6 tailnet address as well as a v4 one.

---

## Step 3 — Install Tailscale

```bash
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/resolute.noarmor.gpg \
  | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null

curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/resolute.tailscale-keyring.list \
  | sudo tee /etc/apt/sources.list.d/tailscale.list

sudo apt-get update \
  -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/tailscale.list \
  -o Dir::Etc::sourceparts=/dev/null \
  -o APT::Get::List-Cleanup=0

sudo apt-get install -y tailscale
```

> **Memory warning.** This box has ~405 MiB usable and **no swap**. A full `apt upgrade` (117
> packages) collided with `fwupd` and `packagekit` here and drove it into an OOM livelock —
> journald was starved mid-write and the instance hung for seven minutes before a hard reset.
> Stop `fwupd` and `packagekit` before any apt work, and scope `apt-get update` to a single
> source list so unrelated upgrades aren't pulled in as a side effect.

---

## Step 4 — Bring up the subnet router

```bash
sudo tailscale up \
  --advertise-routes=10.0.0.0/16 \
  --accept-dns=false \
  --hostname=wishly-vpc-router
```

- `--advertise-routes` offers the route; it does **nothing** until approved (step 5).
- `--accept-dns=false` stops tailscaled rewriting `/etc/resolv.conf` on a server.

One `/16` covers all four subnets, so adding a subnet later needs no route change.

---

## Step 5 — Authenticate and approve the route

1. Visit the login URL printed by `tailscale up`.
2. **Machines → `wishly-vpc-router` → Route settings** → approve `10.0.0.0/16`.
3. While there, **disable key expiry** for this machine.

Advertised routes are inert until a human approves them. Confirm with:

```bash
tailscale status --json | grep PrimaryRoutes    # → ["10.0.0.0/16"]
```

`PrimaryRoutes` means this node is actually serving the subnet. If you later add a second
router advertising the same CIDR, Tailscale elects one primary and fails over automatically.

---

## Step 6 — UDP GRO throughput tuning

```bash
# /etc/networkd-dispatcher/routable.d/50-tailscale   (chmod 755)
#!/bin/sh

ethtool -K ens5 rx-udp-gro-forwarding on rx-gro-list off
```

Tailscale warns about this at startup; default NIC settings measurably cap forwarding
throughput. Installed as a dispatcher hook so it re-applies every boot.

---

## Step 7 — Allow the router to reach RDS

```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-0358d6914bd8d3d7e \
  --protocol tcp --port 5432 \
  --source-group sg-0c1fe6ce553f9aeb3
```

The RDS instance uses the VPC's `default` security group, which only admits traffic from its
own members. The router isn't a member, so connections time out — **including from the router
itself**, which is the quickest way to tell this apart from a Tailscale problem.

> **Reference the source security group, not a Tailscale CIDR.** The router SNATs forwarded
> traffic, so packets arrive from `10.0.11.59` (the router's ENI), never from `100.64.0.0/10`.
> A rule keyed to Tailscale addresses matches nothing. Using `--source-group` rather than
> `10.0.11.59/32` also survives the router's IP changing.

---

## Step 8 (optional) — DNS forwarder for VPC-internal names

**Not required for RDS.** AWS publishes RDS endpoint hostnames in *public* DNS, resolving to the
private IP — `dig @1.1.1.1 wishly-db.<id>.<region>.rds.amazonaws.com` returns
`10.0.134.113` from anywhere. DNS was never the obstacle; routing was, and Tailscale solves that.

This forwarder exists for names that genuinely **don't** resolve publicly: EC2 private DNS
(`ip-10-0-11-59.ec2.internal`), Route 53 private hosted zones, and interface VPC endpoints.

```bash
sudo apt-get install -y dnsmasq
```

```ini
# /etc/dnsmasq.d/vpc-split.conf
listen-address=100.90.214.84
bind-interfaces
no-resolv
server=10.0.0.2
cache-size=300
```

It listens on the router's **tailnet** IP and forwards to the VPC resolver at `10.0.0.2`. To use
it tailnet-wide, add `100.90.214.84` as a split-DNS nameserver in the Tailscale admin console,
restricted to `ec2.internal`.

> **Why not point split DNS straight at `10.0.0.2`?** Two reasons. The VPC resolver only answers
> queries originating inside the VPC — the forwarder's queries qualify because of SNAT, but a
> client's would only if routed through the router. More decisively, see the CIDR overlap below:
> `10.0.0.2` is unreachable from the laptop entirely.

---

## Connecting to the database

`psql` ships with the `libpq` keg and isn't on `PATH` by default:

```bash
/opt/homebrew/opt/libpq/bin/psql \
  "host=wishly-db.<id>.<region>.rds.amazonaws.com \
   port=5432 dbname=postgres user=postgres sslmode=require"
```

- `rds.force_ssl = 1` in the `default.postgres18` parameter group, so **`sslmode=require`
  is mandatory**.
- No initial database was created (`DBName: null`), so you land in `postgres`. Create the
  `wishly` role and database with `infra/sql/create_tenant.sql`, then apply
  `infra/sql/schema.sql` as that role.
- Never hardcode `10.0.134.113`; the IP changes on failover and maintenance.
- Keep the master password in the environment, never in the repo (see `docs/runbooks/secrets.md`).

Beekeeper Studio and DataGrip are both installed and work with the same hostname — no SSH
tunnel or port-forward, since the tailnet route makes the private IP directly addressable.

Quick health check without credentials:

```bash
/opt/homebrew/opt/libpq/bin/pg_isready \
  -h wishly-db.<id>.<region>.rds.amazonaws.com -p 5432
```

---

## Gotcha: home LAN overlaps the VPC CIDR

`gavin-macbook-pro`'s Wi-Fi is `10.0.0.204/24`, so the **home LAN is `10.0.0.0/24` — inside the
VPC's `10.0.0.0/16`.** The local /24 is more specific than the tunnel's /16, so it wins:

```
10.0.0.2    → interface: en0    <REJECT>   ← home Wi-Fi, never reaches the tunnel
10.0.11.59  → interface: utun4  /16        ← Tailscale
```

**VPC addresses `10.0.0.0`–`10.0.0.255` are unreachable from this laptop**, including the VPC
DNS resolver at `10.0.0.2`. The failure is a bare timeout with no diagnostic.

Consequences:

- **Never place a resource in `10.0.0.0/24`.** It will be invisible from the laptop.
- `subnet-05a06e430010ed238` (`10.0.0.0/20`) contains the shadowed range. The router avoided it
  by luck, getting `10.0.11.59`.
- RDS at `10.0.134.113` is unaffected — the private subnets don't overlap.

Permanent fixes, if this becomes painful: renumber the home LAN off `10.0.0.0/24`, or use
Tailscale's `4via6`, which is purpose-built for overlapping ranges.

---

## What survives a reboot

| Setting | Location | Persists |
| --- | --- | --- |
| Source/dest check disabled | EC2 instance attribute | Yes |
| IP forwarding | `/etc/sysctl.d/99-tailscale.conf` | Yes |
| tailscaled autostart | systemd — enabled | Yes |
| Route advertisement | tailscaled prefs | Yes |
| Route approval | Tailscale control plane | Yes |
| UDP GRO tuning | `networkd-dispatcher/routable.d/50-tailscale` | Yes |
| dnsmasq | systemd — enabled | Yes |
| Security group rules | AWS | Yes |
| `fwupd` / `packagekit` stopped | runtime only — **not masked** | **No** — they restart |

---

## Open items

Ordered by how much they'd hurt.

1. **Tailscale key expires 2027-02-25.** Default ~180-day lifetime, still enabled. When it
   lapses the router stops forwarding and the VPC goes dark, with no obvious cause. Disable key
   expiry for this machine in the admin console.
2. **RDS subnet group spans all four subnets.** `default-vpc-082652e0a55804c01` includes
   `subnet-05a06e430010ed238`, so a restore or replacement could land the instance at
   `10.0.0.x` — inside the laptop's dead zone. Create a subnet group with only the two isolated
   private subnets.
3. **`BackupRetentionPeriod: 1`.** One day. Seven is the usual floor.
4. **`DeletionProtection: false`.** One command from gone.
5. **117 package upgrades outstanding**, including security updates. The `.deb` files are already
   cached in `/var/cache/apt/archives`, so finishing is unpack-only — do it with swap added and
   inside `tmux`.
6. **No swap, 405 MiB usable.** The condition behind the original OOM wedge is unchanged.
7. **Single point of failure.** One t4g.nano is the only path into the VPC, on the family's
   lowest network baseline. Fix is a second router advertising the same `10.0.0.0/16`.
8. **Port 22 open to `0.0.0.0/0`.** Deliberately left as a fallback independent of the tailnet.
   Once trusted, narrow it and move SSH onto Tailscale.
9. **Engine drift.** RDS runs Postgres 18.3; `CLAUDE.md` pins `postgres:18.4` for local Docker.
10. **Private subnets have no outbound internet.** A subnet router provides inbound reachability
    only. Anything in `10.0.128.0/20` that needs to `apt install` requires a NAT gateway.

---

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Connection times out from laptop **and** from the router | Security group — not Tailscale |
| Times out from laptop only, works from router | Route not approved, or CIDR overlap (see above) |
| Target address is `10.0.0.x` | Shadowed by the home LAN; it will never work from this laptop |
| Everything worked, then stopped months later | Tailscale node key expired |
| SSH accepts the TCP connection but no banner | Box is thrashing — usually memory pressure |
| `tailscale status` shows the node but no traffic flows | Check `PrimaryRoutes` and source/dest check |
