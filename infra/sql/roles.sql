-- One-time setup for a fresh, self-hosted Postgres: the wishly database and the
-- two roles the app uses. Run it once as a superuser, before schema.sql.
--
-- Two roles, least privilege:
--   wishly_app     — what the API connects as. Reads and writes rows; can't
--                    create, alter or drop tables.
--   wishly_schema  — owns the database and its tables; only for applying
--                    schema.sql by hand.
--
-- Passwords are passed in as psql variables, so they never land in this file:
--
--   APP_PW=$(openssl rand -hex 24) SCHEMA_PW=$(openssl rand -hex 24)
--   docker run --rm -i postgres:18.4 psql "postgresql://postgres:<pw>@<host>:5432/postgres" \
--     -v ON_ERROR_STOP=1 -v app_password="$APP_PW" -v schema_password="$SCHEMA_PW" \
--     < infra/sql/roles.sql
--
-- Keep both passwords in your password manager. The wishly_app one also goes
-- into Infisical (prod, /wishly) as WISHLY_DATABASE_URL.
--
-- Safe to re-run: roles and the database are only created if missing. It does
-- not change an existing role's password; use `alter role ... password` for that.

-- Postgres has no "create role if not exists", so build the statement only when
-- the role is missing and let \gexec run it.
select format('create role wishly_app login password %L', :'app_password')
where not exists (select from pg_roles where rolname = 'wishly_app')
\gexec

select format('create role wishly_schema login password %L', :'schema_password')
where not exists (select from pg_roles where rolname = 'wishly_schema')
\gexec

-- create database can't run inside a transaction or a DO block, so the same trick.
select 'create database wishly owner wishly_schema'
where not exists (select from pg_database where datname = 'wishly')
\gexec

-- The rest happens inside the new database.
\connect wishly

-- Nobody but the two roles may connect.
revoke all on database wishly from public;
grant connect on database wishly to wishly_app, wishly_schema;

-- wishly_schema owns public, so schema.sql can create tables in it.
alter schema public owner to wishly_schema;
revoke create on schema public from public;

-- wishly_app: read and write every table, including ones created later.
-- These two built-in roles cover future tables too, so there's no per-table
-- grant to forget.
grant pg_read_all_data, pg_write_all_data to wishly_app;
