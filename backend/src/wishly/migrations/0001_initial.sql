-- Initial schema. Never edit a migration that has run anywhere; add a new file.

create table users (
    id           text primary key,              -- Clerk user ID (the JWT "sub")
    email        text not null,
    timezone     text not null default 'UTC',   -- IANA name, e.g. America/Chicago
    send_hour    integer not null default 8 check (send_hour between 0 and 23),
    onboarded_at timestamptz,                   -- null until onboarding is done
    created_at   timestamptz not null default now()
);

-- One yearly date and the days before it to send an email, e.g. {7, 1, 0}.
create table reminders (
    id          uuid primary key default gen_random_uuid(),
    user_id     text not null references users (id) on delete cascade,
    title       text not null,
    month       integer not null check (month between 1 and 12),
    day         integer not null check (day between 1 and 31),
    days_before integer[] not null,
    created_at  timestamptz not null default now()
);

create index reminders_user_id_idx on reminders (user_id);

-- Every email sent. The primary key is the duplicate guard: a send only
-- happens after successfully inserting its row, and only one insert can win.
create table sends (
    reminder_id     uuid not null references reminders (id) on delete cascade,
    days_before     integer not null,
    occurrence_date date not null,
    sent_at         timestamptz not null default now(),
    primary key (reminder_id, days_before, occurrence_date)
);
