# Why the database is managed, and why PlanetScale

Production Postgres is **PlanetScale**, reached over the public internet with TLS.

It was considered first as the managed-Postgres option and initially set aside in
favour of RDS, which sat in the same VPC as the AWS hosts and the Tailscale subnet
router that already reached it. That reasoning held right up until the VPC stopped
being the point — once the application containers hold no state, "in the same VPC"
buys nothing that "reachable from anywhere over TLS" does not.

So it came back, and now runs production. What it costs is another vendor on the
critical path for a two-user app. What it buys:

- **No VPC to be inside.** RDS is reachable from its own network; PlanetScale is
  reachable from any host with the DSN. Another host can be brought up to run the
  same containers without having to be placed somewhere specific to reach its
  data, which deletes an entire class of networking from the problem.
- **Branching**, and a hosted WAL story that a `pg_dump` in a bucket is not.
- It is still Postgres — `psql`, `pg_dump`, and `infra/sql/schema.sql` are
  unchanged, so nothing above the DSN had to know about the move.

Kept as a note so the option is not re-litigated from scratch in either
direction. The one hard requirement it added: `?sslmode=require` on the DSN, or
the connection is refused at connect time.
