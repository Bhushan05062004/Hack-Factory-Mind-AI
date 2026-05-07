#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  Factory Mind AI — One-Click Demo Script
#  Builds containers, seeds demo data, prints JWTs, opens UI
# ═══════════════════════════════════════════════════════════
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Factory Mind AI — Conversational Order Management"
echo "  AI-Powered · Precision Manufacturing"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check .env
if [ ! -f .env ]; then
  echo "⚠️  .env not found. Creating from .env.example..."
  cp .env.example .env
  echo "👉  Edit .env and set your GEMINI_API_KEY, then re-run."
  exit 1
fi

# Build and start containers
echo ""
echo "🔨 Building and starting containers..."
docker compose up --build -d

# Wait for API to be healthy
echo ""
echo "⏳ Waiting for API to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is up!"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "❌ API did not start in time. Check logs: docker compose logs api"
    exit 1
  fi
  sleep 2
done

# Seed demo data
echo ""
echo "🌱 Seeding demo data..."
docker exec nova-nexus-api python /app/seed.py

# Show token usage
echo ""
echo "📊 Token usage so far:"
curl -s http://localhost:8000/metrics | python3 -m json.tool 2>/dev/null || echo "  0 tokens (fresh start)"

# Open browser
echo ""
echo "🌐 Opening http://localhost:3000 ..."
if command -v xdg-open > /dev/null; then
  xdg-open http://localhost:3000
elif command -v open > /dev/null; then
  open http://localhost:3000
elif command -v start > /dev/null; then
  start http://localhost:3000
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Factory Mind AI is running!"
echo "  🌐 Frontend: http://localhost:3000"
echo "  🔌 API:      http://localhost:8000"
echo "  📖 Docs:     http://localhost:8000/docs"
echo "  📊 Metrics:  http://localhost:8000/metrics"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Demo accounts:"
echo "  👤 alice@demo.com  (Customer)"
echo "  ⚙️  bob@demo.com    (Operator)"
echo "  ✅ carol@demo.com  (Quality)"
echo ""
