-- Wishly database bootstrap. Creates the login role and the database that
-- infra/sql/schema.sql then populates.
--
-- Run ONCE against a new server, as the RDS master user (or a superuser on a
-- self-hosted Postgres):
--
--   psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -v wishly_password="'...'" -f create_tenant.sql
--
-- Then apply the schema as the wishly role:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema.sql
--
-- The app connects as `wishly`, never as the master user. On RDS the master user
-- is not a true superuser, but it can create roles and databases, which is all
-- this needs. Prefect keeps its own state in Prefect Cloud, so there is no
-- second tenant here.

\set ON_ERROR_STOP on

-- `create role` errors if the role already exists, so guard for re-runs.
select format('create role wishly login password %L', :wishly_password)
where not exists (select 1 from pg_roles where rolname = 'wishly')
\gexec

-- REQUIRED on RDS, and easy to miss on a self-hosted server where you are
-- superuser and it is a no-op.
--
-- The RDS master user is deliberately not a superuser, and Postgres 16+ requires
-- whoever runs `create database ... owner X` to be able to `set role X`. Without
-- this grant the next statement fails with:
--
--   ERROR: must be able to SET ROLE "wishly"
--
-- Creating the role above gives us ADMIN OPTION on it, which is what makes this
-- grant legal. Re-running is harmless: granting an existing membership is a
-- notice, not an error.
grant wishly to current_user;

-- `create database` cannot run inside a transaction or a DO block, so the same
-- \gexec trick applies.
select 'create database wishly owner wishly'
where not exists (select 1 from pg_database where datname = 'wishly')
\gexec

-- Nothing else on this server should be able to enumerate or create objects in
-- the wishly database.
revoke all on database wishly from public;
grant connect on database wishly to wishly;

\echo 'wishly database bootstrap complete'
