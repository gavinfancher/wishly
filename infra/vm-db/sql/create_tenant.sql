-- Wishly tenant bootstrap for the shared homecloud Postgres (DEPLOYMENT-PLAN T1/T2).
--
-- Run ONCE against an existing server, as a superuser:
--   docker exec -i homecloud-postgres psql -U postgres -v ON_ERROR_STOP=1 \
--     -v wishly_password="'...'" -v prefect_password="'...'" < create_tenant.sql
--
-- This is NOT a docker-entrypoint-initdb.d script. Those run only when PGDATA is
-- empty, and this server was initialized long before Wishly existed — an init
-- script would silently never execute.
--
-- Two tenants, two roles: the app never touches Prefect's data and vice versa,
-- and neither is the superuser. That is the shape a managed database would force
-- on us anyway, so we adopt it now.

\set ON_ERROR_STOP on

-- Roles. `create role` errors if it already exists, so guard for re-runs.
select format('create role wishly login password %L', :wishly_password)
where not exists (select 1 from pg_roles where rolname = 'wishly')
\gexec

select format('create role prefect login password %L', :prefect_password)
where not exists (select 1 from pg_roles where rolname = 'prefect')
\gexec

-- Databases. `create database` cannot run inside a transaction or a DO block,
-- so the same \gexec trick applies.
select 'create database wishly owner wishly'
where not exists (select 1 from pg_database where datname = 'wishly')
\gexec

select 'create database prefect owner prefect'
where not exists (select 1 from pg_database where datname = 'prefect')
\gexec

-- Neither tenant should be able to enumerate or create objects in the other's
-- database, nor in the default `postgres` database.
revoke all on database wishly from public;
revoke all on database prefect from public;
grant connect on database wishly to wishly;
grant connect on database prefect to prefect;

\echo 'tenant bootstrap complete'
