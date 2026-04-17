#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting application with hot reload..."
exec "$@"