#!/usr/bin/env bash
# start_server.sh
#
# Starts the WSZ6 dev server, opens the browser to the login page,
# and displays a credentials panel so you can log in immediately.
#
# Usage:
#   bash start_server.sh              # start on port 8000 (default)
#   bash start_server.sh --port 8080  # use a different port
#   bash start_server.sh --no-browser # skip auto-opening the browser
#   bash start_server.sh --help       # show this message

set -e

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DJANGO_DIR="$REPO_ROOT/wsz6_portal"
VENV="$DJANGO_DIR/.venv"
MANAGE="$DJANGO_DIR/manage.py"
LOG_FILE="/tmp/wsz6_server.log"

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
PORT=8000
OPEN_BROWSER=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)      PORT="$2"; shift 2 ;;
        --no-browser) OPEN_BROWSER=false; shift ;;
        --help|-h)
            cat <<'USAGE'
Usage: bash start_server.sh [FLAGS]

Starts the WSZ6 dev server and opens the browser to the login page.

Flags:
  --port PORT      Port to listen on (default: 8000)
  --no-browser     Do not open the browser automatically
  --help, -h       Show this message

Requirements:
  - wsz6_portal/setup_dev.sh must have been run at least once
  - For a fresh test run, use run_phase2_tests.sh first
USAGE
            exit 0 ;;
        *)
            echo "Unknown flag: $1  (use --help for usage)"
            exit 1 ;;
    esac
done

BASE_URL="http://localhost:$PORT"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
BOLD=$'\033[1m'
DIM=$'\033[2m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
RED=$'\033[0;31m'
WHITE=$'\033[1;37m'
RESET=$'\033[0m'

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

if [ ! -f "$DJANGO_DIR/db_uard.sqlite3" ]; then
    echo -e "${YELLOW}WARNING: db_uard.sqlite3 not found.${RESET}"
    echo "The database has not been initialised yet."
    echo "Run:  bash run_phase2_tests.sh --setup-only"
    echo ""
    read -rp "Continue anyway? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || exit 0
fi

# ---------------------------------------------------------------------------
# Activate venv
# ---------------------------------------------------------------------------
# shellcheck source=/dev/null
source "$VENV/bin/activate"
export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development
cd "$DJANGO_DIR"

# ---------------------------------------------------------------------------
# Print credentials panel
# ---------------------------------------------------------------------------
clear
cat <<PANEL
${BOLD}${WHITE}
╔══════════════════════════════════════════════════════════════════╗
║               WSZ6 PORTAL — DEV SERVER                          ║
╠══════════════════════════════════════════════════════════════════╣
║  URL: ${BASE_URL}                                      ║
╠════════════════╦══════════════════╦══════════════════════════════╣
║  Username      ║  Role            ║  Capabilities               ║
╠════════════════╬══════════════════╬══════════════════════════════╣
║  admin         ║  admin_general   ║  Full Django admin panel     ║
║  gameadm       ║  admin_games     ║  Manage games catalog        ║
║  owner1        ║  session_owner   ║  Start & own game sessions   ║
║  owner2        ║  session_owner   ║  Start & own game sessions   ║
║  player1       ║  player          ║  Join sessions               ║
║  player2       ║  player          ║  Join sessions               ║
╠════════════════╩══════════════════╩══════════════════════════════╣
║  Password for all accounts:  ${YELLOW}pass1234${WHITE}                         ║
╠══════════════════════════════════════════════════════════════════╣
║  Quick links                                                     ║
║  ${CYAN}Login page${WHITE}     ${BASE_URL}/accounts/login/              ║
║  ${CYAN}Dashboard${WHITE}      ${BASE_URL}/dashboard/                   ║
║  ${CYAN}Games list${WHITE}     ${BASE_URL}/games/                        ║
║  ${CYAN}Tic-Tac-Toe${WHITE}   ${BASE_URL}/games/tic-tac-toe/            ║
║  ${CYAN}TTT (Visual)${WHITE}  ${BASE_URL}/games/tic-tac-toe-vis/        ║
║  ${CYAN}Mt. Rainier${WHITE}   ${BASE_URL}/games/show-mt-rainier/        ║
║  ${CYAN}Click-Word${WHITE}    ${BASE_URL}/games/click-the-word/         ║
║  ${CYAN}Pixel Probe${WHITE}   ${BASE_URL}/games/pixel-uw-aerial/        ║
║  ${CYAN}Django admin${WHITE}   ${BASE_URL}/admin/                        ║
╚══════════════════════════════════════════════════════════════════╝
${RESET}
${DIM}Test flow (text version):${RESET}
  Browser A  →  log in as ${BOLD}owner1${RESET}, open Tic-Tac-Toe, click "New Session"
  Browser B  →  log in as ${BOLD}player1${RESET}, paste the lobby URL
  owner1 assigns roles (X / O) → clicks "Start Game" → play to end

${DIM}Test flow (interactive vis — M3, Tier-2 canvas regions):${RESET}
  Browser A  →  log in as ${BOLD}owner1${RESET}, open ${CYAN}Cliquez sur l'image${RESET}, click "New Session"
  Run python manage.py install_test_game first if the game is not listed.
  Hover over scene objects to see gold highlights + English label.
  Click the object matching the French word shown in the blue bar.

${DIM}Test flow (visual version — M1):${RESET}
  Browser A  →  log in as ${BOLD}owner1${RESET}, open ${CYAN}Tic-Tac-Toe (Visual)${RESET}, click "New Session"
  Browser B  →  log in as ${BOLD}player1${RESET}, paste the lobby URL
  owner1 assigns roles (X / O) → clicks "Start Game"
  Board should render as SVG (coloured X / O on a 3×3 grid).

PANEL

# ---------------------------------------------------------------------------
# Start server in background
# ---------------------------------------------------------------------------
echo -e "${BOLD}Starting server on port ${PORT}…${RESET}"
python manage.py runserver "$PORT" >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

# Clean up on exit (Ctrl-C, script error, normal exit)
cleanup() {
    echo -e "\n${YELLOW}Stopping server (PID $SERVER_PID)…${RESET}"
    kill "$SERVER_PID" 2>/dev/null
    kill "$TAIL_PID"   2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
    echo -e "${GREEN}Done.${RESET}"
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Wait for server to become responsive
# ---------------------------------------------------------------------------
SPINNER='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
i=0
printf "  Waiting for server"
while ! curl -s "$BASE_URL/" >/dev/null 2>&1; do
    # Exit early if server process already died
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo -e "\n${RED}Server process exited unexpectedly. Log:${RESET}"
        cat "$LOG_FILE"
        exit 1
    fi
    printf "\r  %s Waiting for server…" "${SPINNER:$((i % ${#SPINNER})):1}"
    i=$((i + 1))
    sleep 0.2
done
printf "\r  ${GREEN}Server is ready!${RESET}              \n\n"

# ---------------------------------------------------------------------------
# Open browser
# ---------------------------------------------------------------------------
LOGIN_URL="$BASE_URL/accounts/login/"

if [ "$OPEN_BROWSER" = true ]; then
    echo -e "  Opening ${CYAN}${LOGIN_URL}${RESET} in your browser…"
    if command -v wslview &>/dev/null; then
        wslview "$LOGIN_URL" 2>/dev/null &
    elif command -v cmd.exe &>/dev/null; then
        cmd.exe /c start "" "$LOGIN_URL" 2>/dev/null &
    elif command -v xdg-open &>/dev/null; then
        xdg-open "$LOGIN_URL" 2>/dev/null &
    else
        echo -e "  ${YELLOW}Could not open browser automatically.${RESET}"
        echo -e "  Navigate to: ${BOLD}${LOGIN_URL}${RESET}"
    fi
else
    echo -e "  ${CYAN}${LOGIN_URL}${RESET}"
fi

echo ""
echo -e "${DIM}Server log: $LOG_FILE${RESET}"
echo -e "${DIM}Press Ctrl-C to stop the server.${RESET}"
echo ""

# ---------------------------------------------------------------------------
# Tail server log so output is visible, then wait for server
# ---------------------------------------------------------------------------
tail -f "$LOG_FILE" &
TAIL_PID=$!

wait "$SERVER_PID"
