#!/bin/bash
# Factory Mind AI — Container Startup Script
# Seeds database only if it doesn't exist, then starts the server.

set -e

DATA_DIR="/app/data"
DB_FILE="$DATA_DIR/factory_mind_ai.db"

# Only seed if database doesn't exist yet
if [ ! -f "$DB_FILE" ]; then
    echo "==> First run: seeding database and building FAISS indices..."
    python seed.py
    echo "==> Seeding complete."
else
    echo "==> Database already exists, skipping seed."
fi

echo "==> Starting Factory Mind AI server..."
exec uvicorn app:app --host 0.0.0.0 --port 8000
