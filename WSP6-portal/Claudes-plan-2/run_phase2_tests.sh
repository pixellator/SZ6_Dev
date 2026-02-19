#!/usr/bin/env bash
# run_phase2_tests.sh
#
# Resets the dev environment and starts the server for the Phase 2 manual
# test sequence (lobby → game → GDM log).
#
# Usage:
#   bash run_phase2_tests.sh              # fresh reset + start server
#   bash run_phase2_tests.sh --no-reset  # skip DB wipe, just migrate + seed
#   bash run_phase2_tests.sh --setup-only  # reset + seed, do NOT start server
#
# Run from the repo root (Claudes-plan-2/) or from anywhere – the script
# resolves paths relative to its own location.

set -e

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DJANGO_DIR="$REPO_ROOT/wsz6_portal"
VENV="$DJANGO_DIR/.venv"
MANAGE="$DJANGO_DIR/manage.py"

# GDM_ROOT: three levels above the Django project dir (matches base.py default)
# DJANGO_DIR/.../SZ6_Dev/gdm  →  REPO_ROOT/../../.. = SZ6_Dev
SZ6_DEV_DIR="$(cd "$DJANGO_DIR/../../.." && pwd)"
GDM_DIR="$SZ6_DEV_DIR/gdm"

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
DO_RESET=true
START_SERVER=true

for arg in "$@"; do
    case "$arg" in
        --no-reset)    DO_RESET=false ;;
        --setup-only)  START_SERVER=false ;;
        --help|-h)
            cat <<'USAGE'
Usage: bash run_phase2_tests.sh [FLAGS]

Resets the dev environment and runs the Phase 2 manual test sequence setup.

Flags:
  (none)         Wipe DBs + GDM logs, migrate, seed, start server  [default]
  --no-reset     Skip DB/GDM wipe; just migrate, seed, start server
  --setup-only   Reset + seed but do NOT start the server
  --help, -h     Show this message

Requirements:
  - Run from Claudes-plan-2/ (or any directory; paths are resolved automatically)
  - wsz6_portal/setup_dev.sh must have been run at least once first
USAGE
            exit 0
            ;;
        *)
            echo "Unknown flag: $arg  (use --help to see usage)"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
RESET='\033[0m'

step() { echo -e "\n${BOLD}${CYAN}>>> $*${RESET}"; }
ok()   { echo -e "${GREEN}    OK${RESET}"; }
warn() { echo -e "${YELLOW}    $*${RESET}"; }

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
if [ ! -f "$MANAGE" ]; then
    echo -e "${RED}ERROR: manage.py not found at $MANAGE${RESET}"
    echo "Run this script from the Claudes-plan-2/ repo root."
    exit 1
fi

if [ ! -d "$VENV" ]; then
    echo -e "${RED}ERROR: Virtual environment not found at $VENV${RESET}"
    echo "Run wsz6_portal/setup_dev.sh first."
    exit 1
fi

echo -e "\n${BOLD}=== WSZ6 Phase 2 Test Setup ===${RESET}"
echo "    Repo root : $REPO_ROOT"
echo "    Django dir: $DJANGO_DIR"
echo "    GDM dir   : $GDM_DIR"
echo "    Reset DBs : $DO_RESET"
echo "    Start srv : $START_SERVER"

# ---------------------------------------------------------------------------
# Activate venv
# ---------------------------------------------------------------------------
step "Activating virtual environment"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
ok

export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development
cd "$DJANGO_DIR"

# ---------------------------------------------------------------------------
# Optional reset
# ---------------------------------------------------------------------------
if [ "$DO_RESET" = true ]; then
    step "Wiping SQLite databases"
    for db in db_uard.sqlite3 db_gdm.sqlite3; do
        if [ -f "$db" ]; then
            rm "$db"
            echo "    Removed $db"
        else
            warn "$db not found – skipping"
        fi
    done
    ok

    step "Wiping GDM log directory ($GDM_DIR)"
    if [ -d "$GDM_DIR" ]; then
        rm -rf "$GDM_DIR"
        echo "    Removed $GDM_DIR"
    else
        warn "GDM dir not found – nothing to wipe"
    fi
    ok
fi

# ---------------------------------------------------------------------------
# Migrate
# ---------------------------------------------------------------------------
step "Running migrations"
python manage.py migrate --run-syncdb 2>&1 | grep -E '(Apply|Unapply|OK|No migrations|Running|Creating)'
ok

# ---------------------------------------------------------------------------
# Seed dev data
# ---------------------------------------------------------------------------
step "Creating dev users (admin / gameadm / owner1 / owner2 / player1 / player2)"
python manage.py create_dev_users
ok

step "Installing Tic-Tac-Toe test game"
python manage.py install_test_game
ok

# ---------------------------------------------------------------------------
# django check
# ---------------------------------------------------------------------------
step "Running manage.py check"
python manage.py check
ok

# ---------------------------------------------------------------------------
# Print manual test instructions
# ---------------------------------------------------------------------------
cat <<'INSTRUCTIONS'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PHASE 2 MANUAL TEST SEQUENCE
  All passwords: pass1234
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  [STEP 1]  Browser A – log in as owner1
            http://localhost:8000/accounts/login/

  [STEP 2]  Browser A – open the Tic-Tac-Toe game detail page
            http://localhost:8000/games/tic-tac-toe/
            Click "▶ New Session"  →  you land on the lobby.

  [STEP 3]  Browser B – log in as player1 (or owner2)
            Paste the lobby URL from Browser A's address bar.
            You appear in "Connected Players" on Browser A.

  [STEP 4]  Browser A (owner1) – assign roles:
            • Click a player chip → "Assign here" for role X
            • Click the other player → "Assign here" for role O
            Click "▶ Start Game"

  [STEP 5]  Both browsers redirect to the game page.
            Play Tic-Tac-Toe to completion.

  [STEP 6]  After the game ends, verify:
            • GDM log exists:
              SZ6_Dev/gdm/tic-tac-toe/sessions/<key>/playthroughs/<id>/log.jsonl
            • Admin sessions list shows the session as "Completed":
              http://localhost:8000/admin/   (log in as admin / pass1234)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INSTRUCTIONS

# ---------------------------------------------------------------------------
# Start server (unless --setup-only)
# ---------------------------------------------------------------------------
if [ "$START_SERVER" = true ]; then
    echo -e "${BOLD}${GREEN}Starting development server on http://localhost:8000/${RESET}"
    echo -e "(Press Ctrl-C to stop)\n"
    python manage.py runserver
else
    echo -e "${BOLD}${GREEN}Setup complete. Start the server when ready:${RESET}"
    echo ""
    echo "    cd wsz6_portal"
    echo "    source .venv/bin/activate"
    echo "    DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development python manage.py runserver"
    echo ""
fi
