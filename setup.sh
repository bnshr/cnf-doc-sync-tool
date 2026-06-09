#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

echo "=== CNF Doc Sync — Setup ==="
echo ""

# Check prerequisites
missing=()
command -v python3 >/dev/null 2>&1 || missing+=("python3 (3.11+)")
command -v node >/dev/null 2>&1    || missing+=("node (18+)")
command -v gh >/dev/null 2>&1      || missing+=("gh (GitHub CLI — https://cli.github.com)")

if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing prerequisites:"
  for m in "${missing[@]}"; do
    echo "  - $m"
  done
  exit 1
fi

# Python backend
echo "[1/3] Setting up Python backend..."
if command -v uv >/dev/null 2>&1; then
  uv venv 2>/dev/null || true
  source .venv/bin/activate
  uv pip install -e . --quiet
else
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -e . --quiet
fi

# Frontend
echo "[2/3] Building frontend..."
cd frontend
npm install --silent
npm run build
cd ..

# Verify
echo "[3/3] Verifying..."
source .venv/bin/activate
python -c "from cnf_doc_sync_ui.server import app; print('  Backend: OK')"
[ -f cnf_doc_sync_ui/static/index.html ] && echo "  Frontend: OK" || echo "  Frontend: MISSING"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Register and install the Claude Code plugin:"
echo "     claude plugin marketplace add $REPO_DIR"
echo "     claude plugin install cnf-doc-sync"
echo ""
echo "  2. Open Claude Code and run:"
echo "     /cnf-doc-sync <private-commit-hash>"
echo ""
