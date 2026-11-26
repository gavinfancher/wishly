-- One-time setup for a fresh Postgres: the wishly database and its one role.
-- Run it once as the superuser, before schema.sql.
--
-- One role, `wishly`, like the other apps on the shared Postgres (nextup, homecloud):
-- it owns the database and its tables, the API connects as it, and you apply
-- schema.sql as it.
--
-- Paste into pgcli, putting a fresh password where <pw> is (openssl rand -hex 24):
--
--   pgcli -h postgres.ad.gavinf.com -U postgres
--
-- Keep the password in your password manager. It also goes into Infisical
-- (wishly project, prod) as WISHLY_DATABASE_URL.
--
-- Moving a server that still has the old wishly_app / wishly_schema roles?
-- Use migrate-one-role.sql instead.

-- LOGIN matters: without it the API gets `role "wishly" is not permitted to log in`.
create role wishly login password '<pw>';
create database wishly owner wishly;

\c wishly

-- Only wishly and the shared backup role may connect.
revoke all on database wishly from public;
grant connect on database wishly to wishly, backup;

-- wishly owns public, so schema.sql can create tables in it. Nobody else can.
alter schema public owner to wishly;
revoke create on schema public from public;
