# PlanetScale — not used

Considered as the managed-Postgres option and set aside in favour of RDS, which
sits in the same VPC as the standby EC2 and the Tailscale subnet router that
already reaches it.

Kept as a note so the option is not re-litigated from scratch: the appeal was
branching and the hosted WAL story, and the cost was another vendor on the
critical path for a single-user app whose recovery plan is a `pg_dump` in a
bucket.
