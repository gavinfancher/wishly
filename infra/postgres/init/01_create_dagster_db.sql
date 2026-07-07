-- runs once on first cluster init (mounted into /docker-entrypoint-initdb.d).
-- dagster's run/event/schedule storage lives in its own database so its
-- alembic_version table never collides with the app's alembic migrations.
create database wishly_dagster;
