-- Runs once, on first initialisation of the Postgres volume.
--
-- POSTGRES_DB creates the development database. This adds the second one the
-- test suite needs, because backend/tests/conftest.py refuses to start against
-- any database whose name does not end in `_test` — an interlock added after
-- pointing the suite at the development database once destroyed live data.
--
-- Empty on purpose: the suite applies infra/sql/schema.sql itself (see the
-- _create_schema fixture), so what it needs here is the database, not a schema.
CREATE DATABASE wishly_test;
