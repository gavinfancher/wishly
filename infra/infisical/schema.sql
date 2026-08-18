CREATE TABLE widgets (
    id serial PRIMARY KEY,
    name text,
    created_at timestamptz DEFAULT now()
);
