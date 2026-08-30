# Original brief

The unedited note this project started from, kept as written. Worth leaving in:
the failover design below — a detection node on AWS watching the PVE cluster,
triggering EC2 for compute and RDS for data — was scoped out at one point and is
now the actual target. See [DEPLOYMENT-PLAN.md](DEPLOYMENT-PLAN.md).

---
i would like to make this app deployable to friends and family! 


deployment strategy:
- compute api contianer on vm on local pve at my house
- postgres db vm on local pve
- secrets management on infisical cloud
- s3 for object store if needed
- lambda for accoutn creation (need to work out details here)
- clerk for auth
- prefect on vm local pve (not sure hwo this works yet)
- failure detection node on aws (ecs or ec2, just checks health of pve cluster vms and can trigger failover to ec2 for compute and rds for data base)
- hourly pg-dump backups to s3 (only keep the last 48 dumps)
- cloudflare for cdn
- react/vite front end
    - i want a static front end that just makes encrypted api calls thru cloudflare tunnel
