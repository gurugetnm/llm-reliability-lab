-- Runs once, on first container init, against POSTGRES_DB.
-- pgvector ships with the pgvector/pgvector image but the extension
-- still needs to be created explicitly per-database.
CREATE EXTENSION IF NOT EXISTS vector;

-- A separate database for the test suite (apps/api/tests), so pytest
-- never creates/drops tables in the database docker-compose's api
-- service and local development actually use. Named by convention —
-- if you rename POSTGRES_DB, update this to match.
SELECT 'CREATE DATABASE llm_reliability_lab_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'llm_reliability_lab_test')\gexec

\c llm_reliability_lab_test
CREATE EXTENSION IF NOT EXISTS vector;
