#!/bin/bash
# ══════════════════════════════════════════════════════
#  NoteVerse — One-Click Launcher (Mac / Linux)
# ══════════════════════════════════════════════════════

# Move to the folder this script lives in (no matter where you run it from)
cd "$(dirname "$0")"

echo ""
echo "🚀  NoteVerse — AI Notes Platform"
echo "══════════════════════════════════"

# ── 1. Check Python ────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌  Python 3 not found. Install it from https://python.org and re-run."
  exit 1
fi
echo "✅  Python: $(python3 --version)"

# ── 2. Create virtual-env (first run only) ─────────────
if [ ! -d "venv" ]; then
  echo "📦  Creating virtual environment..."
  python3 -m venv venv
fi

# ── 3. Activate virtual-env ───────────────────────────
source venv/bin/activate

# ── 4. Install / upgrade dependencies ─────────────────
echo "📥  Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅  Dependencies ready."

# ── 5. Ensure uploads directory exists ────────────────
mkdir -p static/uploads

# ── 6. Anthropic API key (optional) ───────────────────
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "⚠️   ANTHROPIC_API_KEY is not set."
  echo "    AI features (summaries, chat, smart search) will show a warning."
  echo "    To enable them, run:"
  echo "      export ANTHROPIC_API_KEY=sk-ant-your-key-here"
  echo "    then re-run this script."
  echo ""
fi

# ── 7. Launch Flask ───────────────────────────────────
echo ""
echo "🌐  Starting server at http://localhost:5000"
echo "    Press Ctrl+C to stop."
echo ""

python3 app.py
