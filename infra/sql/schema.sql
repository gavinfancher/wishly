-- Wishly application schema — the single source of truth for the database.
--
-- Apply to a fresh database (idempotent, safe to re-run):
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f infra/sql/schema.sql
--
-- This file and the SQLAlchemy models in backend/src/wishly/db/models.py must
-- agree. Nothing generates one from the other — instead **the test suite builds
-- its database from this file**, so a model that has drifted from it fails the
-- tests immediately rather than in production. Change both together.
--
-- There are no migrations. `create table if not exists` creates what is missing
-- and leaves what exists untouched — it will NOT alter an existing table. On a
-- database that already holds data, a column change is hand-written SQL applied
-- before this file is re-run.

-- gen_random_uuid() is core in Postgres 13+, but pgcrypto keeps this working on
-- older servers and costs nothing where it is already built in.
create extension if not exists pgcrypto;

create table if not exists suppressions (
    email      text not null,
    reason     text not null,
    created_at timestamp with time zone default now() not null,
    constraint pk_suppressions primary key (email)
);

create table if not exists users (
    id           text not null,
    email        text not null,
    first_name   text,
    last_name    text,
    timezone     text default 'UTC' not null,
    send_hour    integer default 8 not null,
    onboarded_at timestamp with time zone,
    deleted_at   timestamp with time zone,
    created_at   timestamp with time zone default now() not null,
    updated_at   timestamp with time zone default now() not null,
    constraint pk_users primary key (id),
    constraint ck_users_send_hour_range check (send_hour between 0 and 23)
);

create table if not exists templates (
    id         uuid default gen_random_uuid() not null,
    user_id    text,
    name       text not null,
    subject    text not null,
    html       text not null,
    created_at timestamp with time zone default now() not null,
    constraint pk_templates primary key (id),
    constraint fk_templates_user_id_users foreign key (user_id)
        references users (id) on delete cascade
);

create table if not exists test_email_log (
    id         uuid default gen_random_uuid() not null,
    user_id    text not null,
    status     text not null,
    resend_id  text,
    error      text,
    created_at timestamp with time zone default now() not null,
    sent_at    timestamp with time zone,
    constraint pk_test_email_log primary key (id),
    constraint fk_test_email_log_user_id_users foreign key (user_id)
        references users (id) on delete cascade
);

create index if not exists ix_test_email_log_user_id on test_email_log (user_id);

create table if not exists events (
    id              uuid default gen_random_uuid() not null,
    user_id         text not null,
    title           text not null,
    event_type      text not null,
    event_month     integer not null,
    event_day       integer not null,
    event_year      integer,
    message         text,
    recipient_email text,
    recipient_name  text,
    template_id     uuid,
    is_active       boolean default true not null,
    created_at      timestamp with time zone default now() not null,
    updated_at      timestamp with time zone default now() not null,
    constraint pk_events primary key (id),
    constraint ck_events_event_month_range check (event_month between 1 and 12),
    constraint ck_events_event_day_range check (event_day between 1 and 31),
    constraint fk_events_user_id_users foreign key (user_id)
        references users (id) on delete cascade,
    constraint fk_events_template_id_templates foreign key (template_id)
        references templates (id)
);

create index if not exists events_user_id_idx on events (user_id);

-- Partial index: the send pipeline only ever scans active events.
create index if not exists events_month_day_idx
    on events (event_month, event_day) where is_active;

create table if not exists event_reminders (
    id          uuid default gen_random_uuid() not null,
    event_id    uuid not null,
    days_before integer not null,
    constraint pk_event_reminders primary key (id),
    constraint ck_event_reminders_days_before_range check (days_before between 0 and 365),
    constraint event_id_days_before unique (event_id, days_before),
    constraint fk_event_reminders_event_id_events foreign key (event_id)
        references events (id) on delete cascade
);

-- The idempotency ledger. The unique constraint below is what makes a double
-- send structurally impossible: the sender never sends without first winning
-- `insert ... on conflict (event_id, days_before, occurrence_date) do nothing`.
create table if not exists notification_log (
    id              uuid default gen_random_uuid() not null,
    event_id        uuid not null,
    days_before     integer not null,
    occurrence_date date not null,
    status          text default 'pending' not null,
    resend_id       text,
    error           text,
    created_at      timestamp with time zone default now() not null,
    sent_at         timestamp with time zone,
    constraint pk_notification_log primary key (id),
    constraint event_id_days_before_occurrence_date
        unique (event_id, days_before, occurrence_date),
    constraint fk_notification_log_event_id_events foreign key (event_id)
        references events (id) on delete cascade
);
