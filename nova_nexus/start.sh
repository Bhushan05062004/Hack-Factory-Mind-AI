#!/usr/bin/env bash
# Quick-start script for Factory Mind AI OMS
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Factory Mind AI — Conversational Order Management"
echo "  DSATM Hackathon 2025"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check .env
if [ ! -f .env ]; then
  echo "⚠️  .env not found. Copying from .env.example..."
  cp .env.example .env
  echo "👉  Edit .env and add your OPENAI_API_KEY, then re-run."
  exit 1
fi

# Install deps
echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

# Launch
echo "🚀 Starting server at http://localhost:8000"
python main.py
