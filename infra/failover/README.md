# Failover

The AWS side of [docs/DEPLOYMENT-PLAN.md](../../docs/DEPLOYMENT-PLAN.md): keeping
Wishly reachable when the home Proxmox cluster is not.

The design is deliberately small, because the database left the house first.
Postgres is RDS, so both the home host and the standby EC2 are **stateless**
application hosts pointed at the same database. A failover therefore moves compute
and nothing else — nothing is promoted, replicated, or reconciled.

```
detection-script/   watches the Proxmox node on the tailnet; exit 1 == down
planetscale/        discarded alternative, kept for the reasoning
```

## The sequence

1. `detection-script` stops seeing the Proxmox node and exits 1.
2. Whatever supervises it (a systemd unit with `OnFailure=`) starts the standby EC2.
3. That instance boots the same `infra/compose.yaml`, renders `infra/.env` from
   Infisical, and connects to the same RDS.
4. `cloudflared` there registers the tunnel, and `api.wishly.dev` follows.
5. Prefect Cloud hands the standby's worker any runs that went unclaimed — the
   schedule lives in Cloud precisely so it survives the host it schedules.

## Not built yet

Step 2 is the gap: the detector reports, but nothing acts on the report. See
**T2** in the deployment plan for the `ec2:StartInstances` role, and for the
decision that has to be made first — whether the standby is safe to run *while*
home is still up. Two `cloudflared` instances on one tunnel both register, and two
workers on one deployment both poll. The send stays correct either way, because
`notification_log`'s unique constraint makes a double send impossible, but
"correct" and "intended" are not the same thing.
