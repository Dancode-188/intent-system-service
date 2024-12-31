#!/bin/bash
set -e

# Wait for TimescaleDB to be ready
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "timescaledb" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q'; do
  echo "TimescaleDB is unavailable - sleeping"
  sleep 1
done

echo "TimescaleDB is up - executing schema setup"
PGPASSWORD=$POSTGRES_PASSWORD psql -h "timescaledb" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/db_setup.sql