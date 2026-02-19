#!/usr/bin/env bash
# setup_dev.sh
#
# Run this script once after Python 3.11, Redis, and PostgreSQL are
# installed.  It creates a virtual environment, installs dependencies,
# copies the dev .env file, and runs the initial migrations.
#
# Usage:
#   cd wsz6_portal
#   bash setup_dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== WSZ6-portal development setup ==="

# 1. Create virtual environment with Python 3.11
if [ ! -d ".venv" ]; then
    echo "[1/5] Creating virtual environment (.venv) with Python 3.11..."
    python3.11 -m venv .venv
else
    echo "[1/5] Virtual environment already exists – skipping."
fi

# 2. Activate and upgrade pip
echo "[2/5] Activating virtual environment and upgrading pip..."
source .venv/bin/activate
pip install --upgrade pip --quiet

# 3. Install Python dependencies
echo "[3/5] Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

# 4. Copy .env.dev to .env if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "[4/5] Copying .env.dev -> .env ..."
    cp .env.dev .env
    echo "      NOTE: Edit .env before running in production!"
else
    echo "[4/5] .env already exists – skipping copy."
fi

# 5. Apply migrations (SQLite mode, no PostgreSQL needed)
echo "[5/5] Running initial migrations..."
python manage.py migrate

echo ""
echo "=== Setup complete! ==="
echo ""
echo "To start the development server:"
echo "  source .venv/bin/activate"
echo "  python manage.py runserver"
echo ""
echo "To verify WebSocket: visit http://localhost:8000/play/echo-test/"
echo ""
echo "To enable PostgreSQL/Redis, set USE_POSTGRES=true and USE_REDIS=true in .env"
echo "and run: python manage.py migrate"
