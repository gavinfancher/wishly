-- One-time move of the live database (postgres.ad.gavinf.com) from the old two roles
-- (wishly_app + wishly_schema) to the single `wishly` role. A fresh server doesn't
-- need this; it uses roles.sql. Done 2026-11-26.
--
-- Paste each step into pgcli as the superuser, connected to the wishly database:
--
--   pgcli -h postgres.ad.gavinf.com -U postgres -d wishly

-- Step 0: the role. It must have LOGIN, or the API gets
-- `role "wishly" is not permitted to log in`.
create role wishly login password '<pw>';
select rolname, rolcanlogin from pg_roles where rolname = 'wishly';   -- want True

-- Step 1: everything wishly_schema owned (the database, schema public, the four
-- tables and their sequences) now belongs to wishly. The data isn't touched.
reassign owned by wishly_schema to wishly;
select tablename, tableowner from pg_tables where schemaname = 'public';   -- all wishly

-- Then set WISHLY_DATABASE_URL in Infisical (wishly-tg-hh, prod) to
-- postgresql://wishly:<pw>@postgres.ad.gavinf.com:5432/wishly, wait for the pods to
-- roll, and check https://api.wishly.dev/readyz.

-- Step 2: remove the old roles. drop owned also revokes their grants (CONNECT,
-- pg_read_all_data / pg_write_all_data), which would otherwise block drop role.
drop owned by wishly_app, wishly_schema;
drop role wishly_app;
drop role wishly_schema;
