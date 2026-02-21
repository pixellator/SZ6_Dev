# Researcher Panel — Prototype Complete

**Prepared by:** Claude Sonnet 4.6
**Date:** 2026-02-21
**Context:** WSZ6-portal Phase 5 — Research Data Access (R1–R7)
**Commit:** `888f753`

All seven milestones from `Researcher-panel-dev-plan.md` have been implemented,
tested against `manage.py check` (0 issues), migrated, and pushed to `origin/master`.

---

## Milestone Summary

### R1 — Session List Dashboard ✓

**Completion criterion met:** A research admin can log in, navigate to `/research/`,
and see a paginated, filterable list of all game sessions.

**What was built:**

- **View** `research_dashboard` — queries `GameSession` from UARD with five optional
  GET filters: `game` (slug), `status`, `date_from`, `date_to`, `owner` (username
  substring). Paginates at 25 sessions per page.
- **Cross-database annotation** — for each page of sessions, a single GDM query
  (`PlayThrough.objects.using('gdm').filter(...).values('session_key').annotate(count=...)`)
  fetches playthrough counts and attaches them to each session row in O(1) per session.
- **Template** `research/dashboard.html` — GET filter form (game dropdown, status
  dropdown, date pickers, owner text field), paginated session table showing game name,
  start time, status badge, owner, and playthrough count. Pagination links preserve all
  active filters. Quick-links to "My Annotations" and "API Token" in the page header.
- **Access control** — all research views guard with `_require_research(request)`, which
  calls `WSZUser.can_access_research()` and returns HTTP 403 for non-research users.

**Files:**
- `wsz6_admin/research/views.py` — `research_dashboard`
- `wsz6_admin/research/urls.py` — `path('', ...)`
- `templates/research/dashboard.html`

---

### R2 — Session Detail ✓

**Completion criterion met:** Clicking any session opens a detail page showing
session metadata and all play-throughs for that session.

**What was built:**

- **View** `session_detail` — fetches the `GameSession` from UARD (game, owner,
  status, timestamps, `summary_json`) and all `PlayThrough` records for the session
  from GDM, ordered by `started_at`. Play-throughs are numbered 1-based for display.
  Also loads the researcher's session-level annotations from UARD.
- **Template** `research/session_detail.html` — responsive metadata grid (session key,
  owner, status badge, started/ended, playthrough count), collapsible `<details>` block
  for `summary_json`, and an **API Handle bar** with a read-only URL input and a
  "Copy" button that uses `navigator.clipboard.writeText()`.
- **Play-through table** — columns: #, Started, Ended, Outcome (colour-coded), Steps,
  and three action buttons per row: `[View Log]`, `[JSONL]`, `[ZIP]`.
- **Session-level annotation widget** — displays existing notes with delete buttons;
  a `<details>`-collapsible form to add new notes (no JavaScript required). See R6.

**Files:**
- `wsz6_admin/research/views.py` — `session_detail`
- `wsz6_admin/research/urls.py` — `sessions/<uuid:session_key>/`
- `templates/research/session_detail.html`

---

### R3 — Log Viewer ✓

**Completion criterion met:** Clicking "View Log" for a play-through shows all log
events in chronological order, with collapsible state JSON.

**What was built:**

- **View** `log_viewer` — reads `log.jsonl` line-by-line from disk, parses each line
  as JSON (with graceful fallback for malformed lines), and paginates at 50 frames per
  page. Computes previous/next play-through IDs for inter-PT navigation. Loads and
  attaches per-frame annotations (see R6).
- **`_enrich_log_entry` helper** — pre-processes each entry in-place: serialises
  `state` and `role_assignments` dicts to indented JSON strings for template display;
  extracts `artifact_name_safe` and `artifact_version` from artifact events (with
  fallback to regex parsing of the filename).
- **Template** `research/log_viewer.html` — two-column grid: log timeline on the left,
  sticky artifact pane on the right. Each log frame is a card colour-coded by event
  type (11 types handled: `game_started`, `operator_applied`, `undo_applied`,
  `game_ended`, `game_paused`, `game_resumed`, `player_joined`, `player_left`,
  `artifact_created`, `artifact_saved`, `artifact_finalized`; plus `parse_error` and
  a generic fallback). State JSON shown in collapsible `<details>` blocks. Role
  assignments rendered as a table.
- **`export_jsonl` view** (also R5 preview) — serves the raw `log.jsonl` as an
  `application/x-ndjson` file download from the log viewer toolbar.

**Files:**
- `wsz6_admin/research/views.py` — `log_viewer`, `_enrich_log_entry`, `export_jsonl`
- `wsz6_admin/research/urls.py` — `sessions/<key>/<pt_id>/`
- `templates/research/log_viewer.html`

---

### R4 — Artifact Support in GDM Writer ✓

**Completion criterion met:** `GDMWriter.write_artifact()` is implemented; the log
viewer renders artifact events with a working link to the artifact content.

**What was built:**

- **`GDMWriter.write_artifact(artifact_name, content, version)`** — writes two files
  atomically: a versioned snapshot (`artifacts/<name>.v<N>.txt`) and the current
  copy (`artifacts/<name>.txt`). Returns the relative path to the versioned file.
  Uses `asyncio.to_thread` so the async game consumer is not blocked.
- **`GDMWriter.write_artifact_event(event_type, artifact_name, artifact_path, version)`**
  — wraps `write_event` for the three artifact event types (`artifact_created`,
  `artifact_saved`, `artifact_finalized`), using the correct field name (`version` vs
  `final_version`) per event type.
- **View** `artifact_viewer` — path-traversal-safe artifact serving:
  - Validates `artifact_name` against `^[\w\-\.]+$` (no slashes).
  - Resolves the real path with `os.realpath` and confirms it is inside the
    `artifacts/` directory before opening.
  - Returns `JsonResponse` when `?format=json` is set (used by the artifact pane's
    `fetch()` call), or renders `artifact_viewer.html` for direct navigation.
- **Artifact pane in log_viewer.html** — a sticky right-hand panel. Clicking
  "👁 View" on any artifact event calls `loadArtifact(name, version)` in JavaScript,
  which `fetch()`es the `?format=json` endpoint and populates the pane inline without
  a page reload. A "Full view ↗" link opens the standalone HTML view.
- **Template** `research/artifact_viewer.html` — breadcrumb back to the log viewer,
  filename chip, content in a scrollable `<pre>` with purple styling.

**Files:**
- `wsz6_play/persistence/gdm_writer.py` — `write_artifact`, `write_artifact_event`, `_write_text`
- `wsz6_admin/research/views.py` — `artifact_viewer`
- `wsz6_admin/research/urls.py` — `...artifact/<str:artifact_name>/`
- `templates/research/log_viewer.html` — artifact pane + JS fetch
- `templates/research/artifact_viewer.html`

---

### R5 — Export Endpoints ✓

**Completion criterion met:** "Export JSONL" and "Export ZIP" buttons work; downloaded
files are complete and valid.

**What was built:**

- **`export_jsonl`** — streams the raw `log.jsonl` as `application/x-ndjson` with
  `Content-Disposition: attachment`. Filename: `<game-slug>-<key-short>-pt.jsonl`.
- **`export_zip` (per play-through)** — builds an in-memory ZIP (`io.BytesIO` +
  `zipfile.ZipFile`) containing `log.jsonl`, all files in `artifacts/`, and all files
  in `checkpoints/`. Filename: `<game-slug>-<key-short>-pt.zip`.
- **`export_session_zip` (whole session)** — iterates over all play-throughs, nesting
  each under `pt1/`, `pt2/`, … in the archive. Also includes `session_meta.json` from
  the GDM session directory if present. Filename: `<game-slug>-<key-short>-session.zip`.
- **Session detail template** updated with per-row `[JSONL]` and `[ZIP]` buttons and a
  session-level `[↓ Export Entire Session (ZIP)]` footer button.

**Files:**
- `wsz6_admin/research/views.py` — `export_jsonl`, `export_zip`, `export_session_zip`
- `wsz6_admin/research/urls.py` — `export.jsonl`, `export.zip`, session `export.zip`
- `templates/research/session_detail.html` — export buttons

---

### R6 — Researcher Annotations ✓

**Completion criterion met:** A researcher can add, view, and delete annotations at
session, play-through, and frame levels. Annotations persist across browser sessions
and are private to each researcher.

**What was built:**

**Models** (`wsz6_admin/research/models.py`):
- `ResearchAnnotation` — `ForeignKey(researcher)`, `session_key` (UUID), optional
  `playthrough_id` (UUID), optional `log_frame_index` (int), `annotation` (text),
  `created_at`, `updated_at`. Three granularities (session / play-through / frame)
  are distinguished by which optional fields are populated.
- `ResearchAPIToken` — `OneToOneField(researcher)`, `token` (UUID, unique),
  `created_at`, `last_used`, `is_active`. (Also serves R7.)
- Migration `0001_initial` applied to UARD database.

**Views** (5 new):
- `add_annotation` — POST-only; creates a `ResearchAnnotation`; validates and sanitises
  the `next` redirect URL with `_safe_next()` to prevent open redirect.
- `delete_annotation` — POST-only; verifies `pk` belongs to the current researcher
  before deleting.
- `annotation_list` — lists all of the researcher's annotations ordered by newest
  first, grouped visually by level badge.
- `api_token_page` — reads (or reports absence of) the researcher's `ResearchAPIToken`.
- `regenerate_api_token` — POST-only; `get_or_create` then replaces the UUID in-place
  using `save(update_fields=[...])`.

**Annotation UI in templates** (no JavaScript required — pure HTML `<details>` toggle):
- `session_detail.html` — annotation block at the bottom of the session card: lists
  existing notes with timestamps and delete buttons; a `<details>`-collapsible textarea
  to add a new note.
- `log_viewer.html` — play-through-level annotation card between the metadata strip and
  the log timeline; per-frame annotation section inside every frame card (existing notes
  + `<details>` add form, with `#frame-N` fragment in the `next` redirect so the
  browser scrolls back to the annotated frame after submission).
- `annotations.html` — tabular list of all annotations with level badges
  (Session / Play-through / Frame), linked locations, annotation text, date, and delete
  button.
- `api_token.html` — blurred token display with "Reveal & Copy" button (removes CSS
  `filter:blur` and copies to clipboard); "Regenerate" form with confirmation dialog.

**Files:**
- `wsz6_admin/research/models.py`
- `wsz6_admin/research/migrations/0001_initial.py`
- `wsz6_admin/research/views.py` — five new views; `log_viewer` and `session_detail`
  updated to load and pass annotation context
- `wsz6_admin/research/urls.py` — five new patterns
- `templates/research/annotations.html`
- `templates/research/api_token.html`
- `templates/research/session_detail.html` — annotation widget
- `templates/research/log_viewer.html` — annotation widgets

---

### R7 — External REST API and API Tokens ✓

**Completion criterion met:** `GET /api/v1/sessions/` returns valid JSON with Bearer
token auth. A researcher can reproduce the Jupyter Quick Start from the API token page.

**What was built:**

**Authentication** (`wsz6_admin/research/api_auth.py`):
- `ResearchTokenAuthentication(BaseAuthentication)` — reads the
  `Authorization: Bearer <uuid>` header, looks up the corresponding `ResearchAPIToken`
  (must be `is_active=True`), updates `last_used` (best-effort, non-blocking), and
  returns `(researcher, token_obj)`. Returns `None` (not `AuthenticationFailed`) when
  the header is absent, so DRF falls through to `SessionAuthentication` for browser
  access.

**Serializers** (`wsz6_admin/research/serializers.py`):
- `SessionSerializer` — `session_key`, `game_slug`, `game_name`, `owner`, `status`,
  `started_at`, `ended_at`, `summary` (from `summary_json`).
- `PlayThroughSerializer` — `playthrough_id`, `session_key`, `started_at`, `ended_at`,
  `outcome`, `step_count`, `log_url` (JSON endpoint), `jsonl_url` (raw download).

**Permission** (`IsResearcher` in `api_views.py`) — checks `can_access_research()`;
works with both Bearer token and session auth.

**API Views** (`wsz6_admin/research/api_views.py`) — all read-only `GET` endpoints:

| Endpoint | View | Returns |
|---|---|---|
| `GET /api/v1/sessions/` | `APISessionListView` | Paginated sessions; filters: `game`, `status`, `date_from`, `date_to`, `page_size` (max 100) |
| `GET /api/v1/sessions/<key>/` | `APISessionDetailView` | Single session + `playthrough_count` |
| `GET /api/v1/sessions/<key>/playthroughs/` | `APIPlayThroughListView` | All play-throughs for session |
| `GET /api/v1/sessions/<key>/playthroughs/<pt_id>/` | `APIPlayThroughDetailView` | Single play-through |
| `GET /api/v1/sessions/<key>/playthroughs/<pt_id>/log/` | `APILogView` | Parsed log as `{entries: [{index, data}]}` JSON |
| `GET /api/v1/sessions/<key>/playthroughs/<pt_id>/log.jsonl` | `APILogRawView` | Raw JSONL file download |

**URL wiring:**
- `wsz6_admin/research/api_urls.py` — six URL patterns (no `app_name`; registered
  globally so `reverse('api_session_list')` works without namespace prefix).
- Root `wsz6_portal/urls.py` — `path('api/v1/', include('wsz6_admin.research.api_urls'))`.

**Jupyter Quick Start** on `api_token.html` — syntax-highlighted inline code block
showing how to authenticate, list sessions, list play-throughs, fetch a log, and load
it into a Pandas DataFrame. "Copy" button copies the plain-text version to clipboard.

**Files:**
- `wsz6_admin/research/api_auth.py`
- `wsz6_admin/research/serializers.py`
- `wsz6_admin/research/api_views.py`
- `wsz6_admin/research/api_urls.py`
- `wsz6_portal/urls.py` — `api/v1/` include
- `templates/research/api_token.html` — Quick Start code block

---

## Overall File Inventory

| File | Status | Milestone |
|---|---|---|
| `wsz6_admin/research/models.py` | Created | R6 |
| `wsz6_admin/research/migrations/0001_initial.py` | Created | R6 |
| `wsz6_admin/research/views.py` | Replaced stub → extended through R6 | R1–R6 |
| `wsz6_admin/research/urls.py` | Extended | R1–R6 |
| `wsz6_admin/research/api_auth.py` | Created | R7 |
| `wsz6_admin/research/serializers.py` | Created | R7 |
| `wsz6_admin/research/api_views.py` | Created | R7 |
| `wsz6_admin/research/api_urls.py` | Created | R7 |
| `wsz6_play/persistence/gdm_writer.py` | Extended | R4 |
| `wsz6_portal/urls.py` | Extended | R7 |
| `templates/base.html` | Extended (Research nav link) | R1 |
| `templates/research/dashboard.html` | Replaced stub | R1 |
| `templates/research/session_detail.html` | Created | R2, R5, R6 |
| `templates/research/log_viewer.html` | Created | R3, R4, R6 |
| `templates/research/artifact_viewer.html` | Created | R4 |
| `templates/research/annotations.html` | Created | R6 |
| `templates/research/api_token.html` | Created | R6, R7 |

---

## Design Decisions Confirmed in Implementation

1. **Artifacts as separate files, not embedded in the log** — versioned snapshots
   (`<name>.v<N>.txt`) alongside a current copy (`<name>.txt`) in the `artifacts/`
   subdirectory. Log events reference the path; the log is never bloated with content.

2. **Annotations in UARD, not GDM** — `ResearchAnnotation` lives in the default
   (UARD) database. GDM entities are referenced by UUID (no cross-database FK).
   Annotations are private to the creating researcher.

3. **API handle = stable URL + Bearer token** — the handle displayed in the session
   detail is the plain `/api/v1/sessions/<key>/` URL. The token is stored in
   `ResearchAPIToken` and managed from `/research/api-token/`.

4. **No JavaScript required for annotations** — the `<details>` HTML element is used
   for the collapsible add-annotation forms throughout. Only the artifact pane and the
   token reveal/copy button use JavaScript.

5. **Dual-mode artifact viewer** — `?format=json` returns `JsonResponse` for AJAX
   use; omitting it returns a full HTML page. Same view, same auth check, same path
   validation.

---

## Open Items (Deferred from Plan Section 8)

| Item | Notes |
|---|---|
| Shared annotations | Currently private per researcher. Add `visibility` field when needed. |
| Vis rendering in log viewer | Game vis module could be called server-side to render HTML state thumbnails per step. |
| Full-text search over log frames | Client-side JS filter or server-side string match. |
| Pre-built Jupyter notebook template | Distributable `.ipynb` with common analysis patterns. |
| Aggregate analytics views | Grafana integration, session-duration distributions, goal-reach rates. |
