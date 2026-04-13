#!/usr/bin/env bash
# DataPulse — one-command startup script (Linux/macOS)
# Usage: chmod +x scripts/start.sh && ./scripts/start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "  ◈  DataPulse — Talk to Your Data"
echo "  ─────────────────────────────────"
echo ""

# ── Python version check ───────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python || true)
if [ -z "$PYTHON" ]; then
  echo "  ✗ Python not found. Install Python 3.10+ and try again."
  exit 1
fi

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  echo "  ✗ Python $PY_VERSION found, but 3.10+ is required."
  exit 1
fi
echo "  ✓ Python $PY_VERSION"

# ── Node.js version check ──────────────────────────────────────────────────
NODE=$(command -v node || true)
if [ -z "$NODE" ]; then
  echo "  ✗ Node.js not found. Install Node.js 18+ and try again."
  exit 1
fi
NODE_VERSION=$("$NODE" --version | sed 's/v//')
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "  ✗ Node.js v$NODE_VERSION found, but 18+ is required."
  exit 1
fi
echo "  ✓ Node.js v$NODE_VERSION"

# ── GROQ_API_KEY check ───────────────────────────────────────────────────
cd "$ROOT"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  ↳ Created .env from .env.example"
fi

source .env 2>/dev/null || true
if [ -z "$GROQ_API_KEY" ] || [ "$GROQ_API_KEY" = "your_key_here" ]; then
  echo ""
  echo "  ⚠  GROQ_API_KEY is not set."
  echo "     Get a free key at: https://console.groq.com/keys"
  read -rp "  Enter your Gemini API key: " KEY
  if [ -z "$KEY" ]; then
    echo "  ✗ No key provided. Exiting."
    exit 1
  fi
  sed -i.bak "s|GROQ_API_KEY=.*|GROQ_API_KEY=$KEY|" .env
  echo "  ✓ API key saved to .env"
fi
echo "  ✓ GROQ_API_KEY is set"

# ── Python venv + dependencies ─────────────────────────────────────────────
if [ ! -d venv ]; then
  echo "  → Creating Python virtual environment…"
  "$PYTHON" -m venv venv
fi

source venv/bin/activate

echo "  → Installing Python dependencies…"
pip install -q -r requirements.txt 2>&1 | grep -v "^notice" || true
echo "  ✓ Python dependencies ready"

# ── Generate sample datasets if missing ───────────────────────────────────
if [ ! -f assets/samples/sme_lending.csv ]; then
  echo "  → Generating banking sample datasets…"
  python scripts/generate_samples.py
fi
echo "  ✓ Sample datasets ready"

# ── Start backend ──────────────────────────────────────────────────────────
echo "  → Starting backend on http://localhost:8000…"
(cd src/backend && uvicorn main:app --port 8000 2>&1 | sed 's/^/  [backend] /') &
BACKEND_PID=$!

# Wait for backend to be ready
for i in {1..15}; do
  sleep 1
  if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "  ✓ Backend ready"
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo "  ✗ Backend failed to start. Check the output above."
    exit 1
  fi
done

# ── Start frontend ─────────────────────────────────────────────────────────
echo "  → Installing frontend dependencies…"
(cd src/frontend && npm install --silent 2>&1 | grep -v "^npm" || true)
echo "  ✓ Frontend dependencies ready"

echo "  → Starting frontend on http://localhost:3000…"
echo ""
echo "  ┌─────────────────────────────────────────┐"
echo "  │                                         │"
echo "  │   Open http://localhost:3000            │"
echo "  │   in your browser to use DataPulse      │"
echo "  │                                         │"
echo "  │   Press Ctrl+C to stop both servers     │"
echo "  │                                         │"
echo "  └─────────────────────────────────────────┘"
echo ""

# Forward Ctrl+C to kill both processes cleanly
trap "kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM

(cd src/frontend && npm run dev)
