#!/usr/bin/env bash
# install.sh — Set up lm-toolkit on Linux (server) or Git Bash (Windows).
#
# What this does:
#   1. Checks Python 3 and pip
#   2. Installs the `requests` dependency
#   3. Creates ~/.local/bin symlinks for `lm`, `lm-health`, `cronguard`
#   4. Optionally sets LEMONADE_URL and LM_MODEL in ~/.bashrc

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; }

echo ""
echo "lm-toolkit installer"
echo "────────────────────"

# Python
if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  err "Python 3 not found. Install it first."
  exit 1
fi
PY_VERSION=$($PYTHON --version 2>&1)
ok "Python: $PY_VERSION"

# pip
if ! $PYTHON -m pip --version &>/dev/null; then
  err "pip not available. Install python3-pip."
  exit 1
fi
ok "pip available"

# requests
if $PYTHON -c "import requests" 2>/dev/null; then
  ok "requests already installed"
else
  echo "Installing requests..."
  $PYTHON -m pip install --quiet requests
  ok "requests installed"
fi

# ~/.local/bin
mkdir -p "$BIN_DIR"

# lm
cat > "$BIN_DIR/lm" << EOF
#!/usr/bin/env bash
exec $PYTHON "$SCRIPT_DIR/lm.py" "\$@"
EOF
chmod +x "$BIN_DIR/lm"
ok "lm → $SCRIPT_DIR/lm.py"

# lm-health
cat > "$BIN_DIR/lm-health" << EOF
#!/usr/bin/env bash
exec $PYTHON "$SCRIPT_DIR/health.py" "\$@"
EOF
chmod +x "$BIN_DIR/lm-health"
ok "lm-health → $SCRIPT_DIR/health.py"

# cronguard
chmod +x "$SCRIPT_DIR/cronguard.sh"
cat > "$BIN_DIR/cronguard" << EOF
#!/usr/bin/env bash
exec bash "$SCRIPT_DIR/cronguard.sh" "\$@"
EOF
chmod +x "$BIN_DIR/cronguard"
ok "cronguard → $SCRIPT_DIR/cronguard.sh"

# delegate
cat > "$BIN_DIR/lm-delegate" << EOF
#!/usr/bin/env bash
exec $PYTHON "$SCRIPT_DIR/delegate.py" "\$@"
EOF
chmod +x "$BIN_DIR/lm-delegate"
ok "lm-delegate → $SCRIPT_DIR/delegate.py"

# PATH reminder
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  warn "$BIN_DIR is not in your PATH. Add this to ~/.bashrc:"
  echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "── Optional configuration ────────────────────────────────────────────────"
echo ""
echo "Set LEMONADE_URL (default: http://localhost:8000):"
echo "  export LEMONADE_URL=http://localhost:8000"
echo ""
echo "Set LM_MODEL to validate the expected model:"
echo "  export LM_MODEL=Llama-3.2-3B-Hybrid"
echo ""
echo "Set your ntfy.sh topic for cronguard notifications:"
echo "  export NTFY_TOPIC=jf-cronguard"
echo ""
echo "Add all three to ~/.bashrc to persist across sessions."
echo ""
ok "Installation complete. Run: lm --health"
