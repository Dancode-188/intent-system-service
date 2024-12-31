#!/bin/bash
set -e

host="timescaledb"
user="$POSTGRES_USER"
db="$POSTGRES_DB"

until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$host" -U "$user" -d "$db" -c '\q'; do
  >&2 echo "TimescaleDB is unavailable - sleeping"
  sleep 1
done

>&2 echo "TimescaleDB is up - executing command"