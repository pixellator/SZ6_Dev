# WSZ6-Portal Installation Guide — v01

**Date:** 2026-02-19
**For:** Faculty, researchers, and TA administrators setting up WSZ6-portal
on a University of Washington server for LLM-assisted gamification
research and coursework.

---

## What this guide covers

Two deployment modes:

| Mode | When to use | Database | WebSocket layer |
|---|---|---|---|
| **Dev / single-user** | Personal laptop, office workstation, quick demo | SQLite (built-in) | In-memory (built-in) |
| **Shared / multi-user** | Lab server, course deployment, any simultaneous students | PostgreSQL | Redis |

Both modes use the same code and management commands.  Start with Dev mode
and upgrade later if you need concurrent users or persistent session logs.

---

## Prerequisites

### All modes
- **Python 3.11** (`python3.11 --version`)
- **git** (`git --version`)
- **pip** (bundled with Python)

Check Python version:
```bash
python3.11 --version   # must be 3.11.x
```

If Python 3.11 is not installed on a UW departmental Linux server:
```bash
sudo apt install python3.11 python3.11-venv   # Debian/Ubuntu
# or
sudo dnf install python3.11                    # RHEL/Rocky
```

### Shared / multi-user mode only
- **PostgreSQL 14+** — `sudo apt install postgresql postgresql-contrib`
- **Redis 6+** — `sudo apt install redis-server`

---

## 1. Clone the repository

```bash
# Choose a location — /opt or your home directory both work.
git clone https://github.com/pixellator/SZ6_Dev.git SZ6_Dev
cd SZ6_Dev/WSP6-portal/Claudes-plan-2
```

The repository layout relevant to the portal:

```
SZ6_Dev/
  WSP6-portal/
    Claudes-plan-2/           ← repo root (here)
      wsz6_portal/            ← Django project
      start_server.sh         ← dev launcher
      Vis-Features-Dev/       ← game source files
  Textual_SZ6/                ← game formulation sources
  games_repo/                 ← installed game directories (auto-created)
  gdm/                        ← session log storage (auto-created)
```

---

## 2. Run the setup script

```bash
cd wsz6_portal
bash setup_dev.sh
```

This script:
1. Creates `.venv/` (Python 3.11 virtual environment)
2. Installs all dependencies from `requirements.txt`
3. Copies `.env.dev` → `.env` (your local settings file)
4. Runs initial database migrations (creates `db_uard.sqlite3`)

**If `python3.11` is not on `PATH`**, edit line 22 of `setup_dev.sh` to use
the full path, e.g. `/usr/bin/python3.11`.

---

## 3. Configure `.env`

Open `wsz6_portal/.env` in a text editor.  The defaults work for local
dev mode.  Change these values for any shared deployment:

```ini
# Generate a real secret key — run once:
#   python3.11 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DJANGO_SECRET_KEY=<paste-generated-key-here>

# Set to false for production; leave true only on a private dev machine.
DJANGO_DEBUG=true

# Add your server's hostname or IP (comma-separated).
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-server.cs.washington.edu

# Paths to the games repository and session-log storage.
# Defaults resolve to SZ6_Dev/games_repo/ and SZ6_Dev/gdm/ automatically.
# Override only if you want them in a different location:
# GAMES_REPO_ROOT=/data/wsz6/games_repo
# GDM_ROOT=/data/wsz6/gdm
```

---

## 4. Create user accounts

```bash
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development

# Creates admin / gameadm / owner1 / owner2 / player1 / player2
# All with password: pass1234
python manage.py create_dev_users
```

For a real course deployment, create individual student accounts through
the Django admin panel (see §7) or via the management shell:

```bash
python manage.py shell -c "
from wsz6_admin.accounts.models import WSZUser
WSZUser.objects.create_user('netid_here', password='initial_pw', role='player')
"
```

---

## 5. Install the built-in games

```bash
python manage.py install_test_game
```

This copies all game formulation files from `Vis-Features-Dev/game_sources/`
and `Textual_SZ6/` into `games_repo/` and registers them in the database.
Currently installed games include Tic-Tac-Toe, Missionaries & Cannibals,
Pixel Probe (UW aerial image), Click-the-Word (French vocab), and others.

Re-run this command any time you add or update a game source file.

---

## 6. Start the server

### Dev / single-user

```bash
cd ..   # back to Claudes-plan-2/
bash start_server.sh
```

The script activates the venv, prints a credentials panel, starts Django's
development ASGI server on port 8000, and opens the login page in your
browser.  Press Ctrl-C to stop.

```
Browser → http://localhost:8000/accounts/login/
```

### Different port or no auto-browser

```bash
bash start_server.sh --port 8080 --no-browser
```

---

## 7. Django admin panel

Visit `http://localhost:8000/admin/` and log in as `admin` (password `pass1234`).

From here you can:
- Create and manage user accounts (set role to `player`, `session_owner`, etc.)
- View and manage the games catalog
- Browse session logs

---

## 8. LLM-assisted games (API key setup)

Some games (e.g. *Remote LLM Test Game*) call an external LLM API.
Add the key to `.env`:

```ini
# For Gemini:
GEMINI_API_KEY=your-key-here

# For OpenAI (if a future game uses it):
OPENAI_API_KEY=your-key-here
```

Then install the relevant client library inside the venv:

```bash
source .venv/bin/activate
pip install google-genai    # for Gemini
```

The key is read at runtime by the game's formulation file; no server
restart is needed after adding it to `.env` for the first time (a restart
is needed if you change the value while the server is running).

---

## 9. Shared / multi-user deployment (PostgreSQL + Redis)

For a lab server or classroom deployment where multiple students play
simultaneously, upgrade to PostgreSQL and Redis.

### 9.1 Create databases

```bash
sudo -u postgres psql <<'SQL'
CREATE USER wsz6 WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE wsz6_uard OWNER wsz6;
CREATE DATABASE wsz6_gdm  OWNER wsz6;
SQL
```

### 9.2 Update `.env`

```ini
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<generated-key>
DJANGO_ALLOWED_HOSTS=your-server.cs.washington.edu

USE_POSTGRES=true
USE_REDIS=true

UARD_DB_NAME=wsz6_uard
UARD_DB_USER=wsz6
UARD_DB_PASSWORD=choose-a-strong-password
UARD_DB_HOST=localhost
UARD_DB_PORT=5432

GDM_DB_NAME=wsz6_gdm
GDM_DB_USER=wsz6
GDM_DB_PASSWORD=choose-a-strong-password
GDM_DB_HOST=localhost
GDM_DB_PORT=5432

REDIS_URL=redis://127.0.0.1:6379

INTERNAL_API_KEY=<another-random-string>
```

### 9.3 Migrate and collect static files

```bash
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.production

python manage.py migrate
python manage.py collectstatic --no-input
python manage.py create_dev_users    # or create accounts individually
python manage.py install_test_game
```

### 9.4 Run Daphne (ASGI server)

```bash
daphne -b 127.0.0.1 -p 8000 wsz6_portal.asgi:application
```

For a persistent service, create a systemd unit file
(`/etc/systemd/system/wsz6.service`):

```ini
[Unit]
Description=WSZ6 Portal (Daphne ASGI)
After=network.target postgresql.service redis.service

[Service]
User=www-data
WorkingDirectory=/opt/SZ6_Dev/WSP6-portal/Claudes-plan-2/wsz6_portal
EnvironmentFile=/opt/SZ6_Dev/WSP6-portal/Claudes-plan-2/wsz6_portal/.env
Environment=DJANGO_SETTINGS_MODULE=wsz6_portal.settings.production
ExecStart=/opt/SZ6_Dev/WSP6-portal/Claudes-plan-2/wsz6_portal/.venv/bin/daphne \
          -b 127.0.0.1 -p 8000 wsz6_portal.asgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now wsz6
```

### 9.5 nginx reverse proxy (HTTPS required on UW servers)

Create `/etc/nginx/sites-available/wsz6`:

```nginx
server {
    listen 443 ssl;
    server_name your-server.cs.washington.edu;

    ssl_certificate     /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;

    # Static files (served directly by nginx — much faster)
    location /static/ {
        alias /opt/SZ6_Dev/WSP6-portal/Claudes-plan-2/wsz6_portal/staticfiles/;
    }

    # Everything else (including WebSocket upgrade) → Daphne
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 3600;   # keep WebSocket connections alive
    }
}

server {
    listen 80;
    server_name your-server.cs.washington.edu;
    return 301 https://$host$request_uri;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/wsz6 /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

UW departmental servers generally have TLS certificates issued by UW IT;
contact your department's IT contact to obtain one, or use a Let's Encrypt
certificate if the server has a public hostname.

---

## 10. Adding a new game for a course

1. Place the game's `_SZ6.py` and `_WSZ6_VIS.py` files in
   `Vis-Features-Dev/game_sources/` (or `Textual_SZ6/`).
2. Add an entry to `GAME_DEFS` in
   `wsz6_portal/wsz6_admin/games_catalog/management/commands/install_test_game.py`.
3. Run:
   ```bash
   python manage.py install_test_game
   ```
4. The game appears at `http://your-server/games/<slug>/`.

Refer to `Vis-Features-Dev/How-to-Code-Interactive-Visualizations-in-WSZ6.md`
for the full vis file authoring guide.

---

## Quick-reference command cheat sheet

```bash
# Activate the virtualenv (do this first in every new shell)
source wsz6_portal/.venv/bin/activate
export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development   # or .production

# First-time setup
bash wsz6_portal/setup_dev.sh

# Create built-in users and install games
python manage.py create_dev_users
python manage.py install_test_game

# Run dev server (port 8000)
bash start_server.sh

# Run dev server on a different port, no browser
bash start_server.sh --port 8080 --no-browser

# Apply database migrations after a git pull
python manage.py migrate

# Open Django admin shell
python manage.py shell

# Check everything is wired up
python manage.py check
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'django'` | Venv not activated | `source .venv/bin/activate` |
| `ALLOWED_HOSTS` error in browser | Server hostname not in `.env` | Add it to `DJANGO_ALLOWED_HOSTS` and restart |
| WebSocket connects then immediately disconnects | `DJANGO_DEBUG=false` but no Redis configured | Set `USE_REDIS=true` and start Redis, or switch back to dev settings |
| Game page shows text fallback instead of visualization | Vis file not found or import error | Check `games_repo/<slug>/` contains the `_WSZ6_VIS.py` file; re-run `install_test_game` |
| LLM game returns "API error" | Missing or invalid API key | Add key to `.env`; restart server |
| `django.db.utils.OperationalError` on first run | Migrations not applied | `python manage.py migrate` |
| Port 8000 already in use | Previous server still running | `pkill -f daphne` or `pkill -f "manage.py runserver"` |
