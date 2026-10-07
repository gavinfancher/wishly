-- Wishly database schema: the whole thing, in one file.
--
-- Review it, then apply it with the schema role (the API's own role can't
-- create tables), with credentials coming from Infisical:
--
--   infisical run --env=prod -- sh -c \
--     'docker run --rm -i -v /etc/ssl/cert.pem:/etc/ssl/certs/ca-certificates.crt:ro \
--        postgres:18.4 psql "$WISHLY_SCHEMA_DATABASE_URL" -v ON_ERROR_STOP=1' \
--     < infra/sql/schema.sql
--
-- The -v mounts your machine's trusted CA certificates into the container (the
-- postgres image ships without any), so psql can verify PlanetScale's TLS
-- certificate. That's the macOS path; on Linux use /etc/ssl/certs/ca-certificates.crt.
--
-- Safe to re-run: every statement is "if not exists", so a second run changes
-- nothing. It also never changes a table that already exists. To change one,
-- add an explicit `alter table ... ` at the bottom and run the file again.
--
-- Wrapped in a transaction: if any statement fails, none of them apply.

begin;

-- Ids are plain integers the database hands out (1, 2, 3, ...).
create table if not exists users (
    id            bigint generated always as identity primary key,
    email         text not null unique,          -- stored lowercased by the API
    password_hash text not null,                 -- scrypt; see backend/src/wishly/passwords.py
    timezone      text not null default 'UTC',   -- IANA name, e.g. America/Chicago
    send_hour     integer not null default 8 check (send_hour between 0 and 23),
    onboarded_at  timestamptz,                   -- null until onboarding is done
    created_at    timestamptz not null default now()
);

-- One row per signed-in browser. The browser holds a random token; we store only
-- its SHA-256, so a leaked copy of this table can't be used to sign in.
create table if not exists sessions (
    token_hash text primary key,
    user_id    bigint not null references users (id) on delete cascade,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null
);

create index if not exists sessions_user_id_idx on sessions (user_id);

-- One yearly date and the days before it to send an email, e.g. {7, 1, 0}.
create table if not exists reminders (
    id          bigint generated always as identity primary key,
    user_id     bigint not null references users (id) on delete cascade,
    title       text not null,
    month       integer not null check (month between 1 and 12),
    day         integer not null check (day between 1 and 31),
    days_before integer[] not null,
    created_at  timestamptz not null default now()
);

create index if not exists reminders_user_id_idx on reminders (user_id);

-- Every email sent. The primary key is the duplicate guard: a send only
-- happens after successfully inserting its row, and only one insert can win.
create table if not exists sends (
    reminder_id     bigint not null references reminders (id) on delete cascade,
    days_before     integer not null,
    occurrence_date date not null,
    sent_at         timestamptz not null default now(),
    primary key (reminder_id, days_before, occurrence_date)
);

commit;
