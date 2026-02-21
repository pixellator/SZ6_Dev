# Researcher Panel Development Plan

**Prepared by:** Claude Sonnet 4.6
**Date:** 2026-02-21
**Context:** WSZ6-portal Phase 5 — Research Data Access
**Working directory:** `WSP6-portal/Claudes-plan-2/`

---

## 0. Overview and Scope

This plan describes the implementation of the researcher-facing interface for the WSZ6 portal. The target users are **Research Admins** (`ADMIN_RESEARCH` user type), who need to:

1. Browse and filter the full catalogue of game sessions.
2. Drill into a specific session and view its play-through logs step by step.
3. View any document-like artifacts produced during a session.
4. Annotate sessions, play-throughs, and individual log frames with their own notes.
5. Get an API handle (URL + auth token) for any session so they can pipe data into external analytics tools (Jupyter, R, Pandas, etc.).
6. Export raw data files for offline processing.

The research app stub already exists at `wsz6_admin/research/`. All structural prerequisites are in place: `GameSession` records (UARD), `PlayThrough` records (GDM database), `log.jsonl` files (GDM file system), and the `artifacts/` directory is already created by `gdm_writer.ensure_gdm_dirs()`.

---

## 1. Resolved Design Decisions

### 1.1 Artifact Storage (Document-like Outputs)

**Decision: Separate files in `artifacts/`, referenced from the log.**

Rationale:
- Storing full document text on every edit inside `log.jsonl` would bloat the log significantly for open-world games where documents evolve over many steps.
- Pure delta logging inside `log.jsonl` is compact but requires reconstruction logic and complicates the log viewer.
- The `artifacts/` subdirectory already exists at `playthroughs/<id>/artifacts/`.

**Chosen approach:**

```
playthroughs/<playthrough_id>/
    log.jsonl
    checkpoints/
    artifacts/
        <artifact_name>.txt          ← current (latest) version of the document
        <artifact_name>.v1.txt       ← snapshot at first explicit save
        <artifact_name>.v2.txt       ← snapshot at second explicit save
        ...
```

New `GDMWriter` event types for artifacts:

| Event | Fields | Description |
|---|---|---|
| `artifact_created` | `artifact_name`, `artifact_path` | Document artifact created for the first time |
| `artifact_saved` | `artifact_name`, `artifact_path`, `version` | Researcher/player explicitly saved the document; a versioned snapshot is written |
| `artifact_finalized` | `artifact_name`, `artifact_path`, `final_version` | Session ending; final state recorded |

The `artifact_path` is relative to the playthrough directory (e.g., `artifacts/essay.txt`).

The log viewer shows artifact events as clickable entries that open the artifact content in a side pane. The side pane loads the specific versioned file referenced in the log event, so the researcher sees what the document looked like at that point in time (not necessarily the final version).

### 1.2 Annotations

Researcher annotations are **entirely separate from the GDM**. They live in the UARD database (managed by `wsz6_admin`), in a new `ResearchAnnotation` model in the `research` app. They reference GDM entities by key/ID (not by foreign key, since the two databases are separate).

Annotations may be attached at three granularities:
- **Session-level**: references a `session_key`
- **Play-through-level**: references a `session_key` + `playthrough_id`
- **Frame-level**: references a `session_key` + `playthrough_id` + `log_frame_index` (the 0-based line number in the JSONL)

Each annotation belongs to one researcher and is not visible to others by default (annotations are personal research notes, not shared commentary).

### 1.3 External API Handles

A "handle" is a stable URL that external tools can use to retrieve session data via the portal's REST API. It encodes:
```
https://<portal-host>/api/v1/sessions/<session_key>/
```

API authentication for external tools uses **per-researcher API tokens** stored in the UARD (a new `ResearchAPIToken` model). The UI has a "Generate / Reveal API Token" button. The token is sent in the `Authorization: Bearer <token>` header by external clients.

---

## 2. New Models

### 2.1 `research/models.py` — Annotation Model

```python
# wsz6_admin/research/models.py

import uuid
from django.db import models
from django.conf import settings


class ResearchAnnotation(models.Model):
    """A researcher's personal annotation on a session, play-through, or log frame."""

    researcher       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='research_annotations',
    )
    session_key      = models.UUIDField(db_index=True)
    playthrough_id   = models.UUIDField(null=True, blank=True, db_index=True)
    log_frame_index  = models.IntegerField(null=True, blank=True)
    annotation       = models.TextField()
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['session_key', 'playthrough_id', 'log_frame_index', 'created_at']

    def __str__(self):
        level = 'session'
        if self.playthrough_id:
            level = 'playthrough'
        if self.log_frame_index is not None:
            level = f'frame {self.log_frame_index}'
        return f"Annotation by {self.researcher} on {level} {self.session_key}"


class ResearchAPIToken(models.Model):
    """An API access token for a researcher to use with external analytics tools."""

    researcher  = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='research_api_token',
    )
    token       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    last_used   = models.DateTimeField(null=True, blank=True)
    is_active   = models.BooleanField(default=True)

    def __str__(self):
        return f"APIToken for {self.researcher}"
```

---

## 3. URL Structure

Extending `wsz6_admin/research/urls.py`:

```
/research/                                       → session list (dashboard)
/research/sessions/<session_key>/                → session detail
/research/sessions/<session_key>/<playthrough_id>/  → log viewer
/research/sessions/<session_key>/<playthrough_id>/export/  → JSONL download
/research/sessions/<session_key>/<playthrough_id>/export-zip/  → zip (log + artifacts)
/research/sessions/<session_key>/<playthrough_id>/artifact/<artifact_name>/  → artifact viewer
/research/annotations/                           → researcher's annotation list
/research/annotations/<int:pk>/delete/           → delete an annotation
/research/api-token/                             → generate / display API token

/api/v1/sessions/                                → REST: session list
/api/v1/sessions/<session_key>/                  → REST: session detail
/api/v1/sessions/<session_key>/playthroughs/     → REST: playthrough list
/api/v1/sessions/<session_key>/playthroughs/<playthrough_id>/  → REST: playthrough detail
/api/v1/sessions/<session_key>/playthroughs/<playthrough_id>/log/  → REST: log as JSON
/api/v1/sessions/<session_key>/playthroughs/<playthrough_id>/log.jsonl  → REST: raw JSONL
```

---

## 4. Implementation Milestones

---

### R1: Session List Dashboard (~3–4 days)

**Goal:** Replace the stub `research/views.py` with a working filtered session list.

**Views:**
- `research_dashboard(request)`: query `GameSession` from UARD + annotate with `PlayThrough` counts from GDM.

**Filter parameters** (GET query string):
- `game` — filter by game slug
- `status` — one of `open`, `in_progress`, `paused`, `completed`, `interrupted`
- `date_from`, `date_to` — ISO date strings for `started_at` range
- `owner` — filter by username of session owner
- `q` — freetext search over session key

**Template** `research/dashboard.html`:
```
┌─────────────────────────────────────────────────────────────┐
│  Research Dashboard                                 [🔑 API Token] │
├──────┬────────────┬────────┬────────────────┬───────────────┤
│ Game │ Started    │ Status │ Owner          │ Play-throughs │
├──────┼────────────┼────────┼────────────────┼───────────────┤
│  ... │ ...        │ ...    │ ...            │   N  [View]   │
└──────┴────────────┴────────┴────────────────┴───────────────┘
                                     Pagination: < 1 2 3 ... >
```

Filter form is a GET form above the table (no JavaScript required; pure Django form + query string).

**Implementation notes:**
- `PlayThrough` count is fetched by querying the GDM database using `.using('gdm')`, then grouped by `session_key`. A `dict` maps session keys to counts for O(1) annotation of each session row.
- The GDM query uses `PlayThrough.objects.using('gdm').filter(session_key__in=[...]).values('session_key').annotate(count=Count('playthrough_id'))`.
- Access restricted to `request.user.can_access_research()`.

**New URL patterns added:**
```python
path('', views.research_dashboard, name='dashboard'),
```

---

### R2: Session Detail View (~2 days)

**Goal:** Show session metadata and list all play-throughs for a session.

**View:** `session_detail(request, session_key)`

**Data gathered:**
1. `GameSession` from UARD (game name, owner, started/ended, status, summary JSON).
2. All `PlayThrough` records for this session from GDM (`PlayThrough.objects.using('gdm').filter(session_key=session_key).order_by('started_at')`).
3. Researcher's session-level annotations (from `ResearchAnnotation` where `session_key` matches and `playthrough_id` is null).

**Template** `research/session_detail.html`:
```
Session: <uuid>  |  Game: Tic-Tac-Toe  |  Owner: player1
Status: Completed  |  Started: 2026-02-20 14:00  |  Ended: 2026-02-20 14:45

[ Session-level annotation box ]

Play-throughs:
┌─────┬───────────┬────────────┬────────────┬──────────┬────────────────────────────┐
│  #  │ Started   │ Ended      │ Outcome    │ Steps    │ Actions                    │
├─────┼───────────┼────────────┼────────────┼──────────┼────────────────────────────┤
│  1  │ 14:00:01  │ 14:12:33   │ Completed  │ 9        │ [View Log] [Export JSONL]  │
│  2  │ 14:14:00  │ 14:28:11   │ Completed  │ 7        │ [View Log] [Export JSONL]  │
└─────┴───────────┴────────────┴────────────┴──────────┴────────────────────────────┘

[Export All (ZIP)]    [🔗 Copy API Handle]
```

**"Copy API Handle" button:**
A JavaScript `navigator.clipboard.writeText()` call copies the URL
`/api/v1/sessions/<session_key>/` (or the fully qualified URL with domain) to the clipboard. A small tooltip confirms the copy. No backend required.

---

### R3: Log Viewer (~5–6 days)

**Goal:** Parse a `log.jsonl` file and display it as a human-readable step-by-step replay.

**View:** `log_viewer(request, session_key, playthrough_id)`

**Data gathered:**
1. `PlayThrough` record from GDM (for `log_path` and metadata).
2. Read and parse `log.jsonl` (the whole file, or paginated chunks for very long logs).
3. Researcher's frame-level annotations for this playthrough.

**Log parsing:**
```python
def parse_log(log_path):
    """Return list of (index, dict) from a log.jsonl file."""
    entries = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            line = line.strip()
            if line:
                entries.append((i, json.loads(line)))
    return entries
```

**Template** `research/log_viewer.html` layout:
```
┌──────────────────────────────────────────┬──────────────────────┐
│  Log Timeline (left panel)               │  Artifact Pane       │
│                                          │  (right panel,       │
│  Frame 0  [game_started]                 │   shown when         │
│  ├─ Roles: {X: player1, O: player2}      │   frame references   │
│                                          │   an artifact)       │
│  Frame 1  [operator_applied]             │                      │
│  ├─ Step 1: X plays (0,0)                │  essay.txt (v2)      │
│  ├─ Role: 0 (X)                          │  ─────────────────── │
│  └─ [+ Add annotation]                   │  Lorem ipsum dolor   │
│                                          │  sit amet...         │
│  Frame 2  [operator_applied]             │                      │
│  ├─ Step 2: O plays (1,1)                │                      │
│  └─ [+ Add annotation]  [📝 note text]   │                      │
│                                          │                      │
│  Frame N  [game_ended]                   │                      │
│  ├─ Outcome: goal_reached                │                      │
│  └─ Goal message: "X wins!"              │                      │
└──────────────────────────────────────────┴──────────────────────┘
```

**Event rendering:** Each log event type has its own HTML rendering:

| Event type | Display |
|---|---|
| `game_started` | Role assignment table |
| `operator_applied` | Step number, operator name, role, args (if any) |
| `undo_applied` | Step rolled back indicator |
| `game_paused` | Pause marker with timestamp |
| `game_resumed` | Resume marker with checkpoint ID |
| `game_ended` | Outcome badge + goal message |
| `player_joined` | Player name + role |
| `player_left` | Player name departure |
| `artifact_created` | Artifact created, name, link to pane |
| `artifact_saved` | Artifact saved at vN, link to pane |
| `artifact_finalized` | Final document state, link to pane |

**State display:** If the `operator_applied` event includes a `state` field (which the current GDM writer records), it is shown in a collapsible `<details>` block as formatted JSON. In a future enhancement (Phase 5 extension), the game's vis module could be called server-side to render an HTML preview.

**Pagination:** Long logs are displayed in pages of 50 frames. Navigation is via GET parameter `?page=N`. Annotation links include the frame index in the URL fragment so the browser scrolls to the right frame.

**Frame-level annotation form:**
Each frame row has a `[+ Add annotation]` button that reveals a small inline textarea and submit button (no JavaScript required: the form POSTs to `research/annotations/add/` with hidden fields for `session_key`, `playthrough_id`, `log_frame_index`, and then redirects back to the log viewer at the correct page/frame).

---

### R4: Artifact Support in GDM Writer (~2 days)

**Goal:** Add artifact-related event types to `GDMWriter` and support writing/reading artifact files.

**New methods on `GDMWriter`:**

```python
async def write_artifact(
    self,
    artifact_name: str,
    content: str,
    version: int,
) -> str:
    """Write artifact content to a versioned file; returns the relative path."""
    filename = f"{artifact_name}.v{version}.txt"
    artifact_path = os.path.join(self.playthrough_dir, 'artifacts', filename)
    await asyncio.to_thread(self._write_file, artifact_path, content)
    # Also overwrite the "current" (no version suffix) file
    current_path = os.path.join(self.playthrough_dir, 'artifacts', f"{artifact_name}.txt")
    await asyncio.to_thread(self._write_file, current_path, content)
    return os.path.join('artifacts', filename)

async def write_artifact_event(
    self,
    event_type: str,   # 'artifact_created', 'artifact_saved', 'artifact_finalized'
    artifact_name: str,
    artifact_path: str,
    version: int,
) -> None:
    await self.write_event(
        event_type,
        artifact_name=artifact_name,
        artifact_path=artifact_path,
        version=version,
    )

def _write_file(self, path: str, content: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
```

**Artifact viewer view:** `artifact_viewer(request, session_key, playthrough_id, artifact_name, version=None)` — serves the artifact content as a plain text response or renders it in a simple HTML template. If `version` is None, serves the "current" (latest) file. If `version` is given, serves the versioned snapshot.

**Note on document editing operators:** The game consumer already supports `apply_operator` messages from the client. Document-editing games will have operators that pass new document content in the `args` field. The `game_consumer._handle_apply()` code will call `gdm_writer.write_artifact()` when the applied operator produces an artifact update. The exact hook mechanism (e.g., a flag in the operator's metadata or a convention on the returned state) is left for the game formulation developer; the research infrastructure simply records what is written.

---

### R5: Export Endpoints (~2 days)

**Goal:** Allow a researcher to download session data.

**JSONL export:** `export_jsonl(request, session_key, playthrough_id)`
- Authenticates the researcher.
- Looks up `PlayThrough.log_path`.
- Serves the file as `application/x-ndjson` with a `Content-Disposition: attachment` header.
- Filename: `<game_slug>-<session_key_short>-pt<n>.jsonl`.

**ZIP export:** `export_zip(request, session_key, playthrough_id)`
- Builds an in-memory ZIP using `zipfile.ZipFile`.
- Includes: `log.jsonl`, all files in `artifacts/`, all files in `checkpoints/`.
- Streams the ZIP as `application/zip`.
- Filename: `<game_slug>-<session_key_short>-pt<n>.zip`.

**Session-level ZIP:** `export_session_zip(request, session_key)`
- Iterates over all play-throughs for the session.
- Nests each playthrough's files under `pt<n>/` in the archive.
- Also includes `session_meta.json` if present in the GDM session directory.

---

### R6: Researcher Annotations UI (~3 days)

**Goal:** Complete the annotation CRUD cycle in the research views.

**Model:** As defined in Section 2.1 above. Migration required.

**Views added:**
- `add_annotation(request)` — POST-only; adds a `ResearchAnnotation` and redirects back.
- `delete_annotation(request, pk)` — POST-only (no GET); verifies ownership; deletes and redirects.
- `annotation_list(request)` — GET; shows all of the researcher's annotations, grouped by session. Allows navigating back to the log viewer at the annotated frame.

**Session-level annotation widget:** Shown at the top of `session_detail.html`. A simple textarea + Save button. Existing annotations displayed as read-only text with a delete button.

**Play-through-level annotation widget:** Shown at the top of `log_viewer.html`.

**Frame-level annotation widget:** Per-frame `[+ Add annotation]` toggle (pure HTML, no JS — the toggle is done with a `<details>` element around the inline form).

**Annotation display in log viewer:** When a frame has annotations, they are shown inline below the frame content in a styled callout block. Each has a delete button.

---

### R7: External REST API and API Token (~4 days)

**Goal:** Expose session and log data through a versioned REST API authenticated by per-researcher tokens.

**Dependencies:** Django REST Framework (already installed: `djangorestframework` is in the venv as confirmed by `.venv/lib` files).

**API token flow:**
1. Researcher visits `/research/api-token/`.
2. Page shows: current token (masked), "Reveal" button (JavaScript unhide), "Regenerate" button (POST to generate a new UUID, invalidate old one).
3. Token stored in `ResearchAPIToken` model. `last_used` is updated on every API request.

**Authentication class** (`research/api_auth.py`):
```python
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import ResearchAPIToken

class ResearchTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return None
        token_str = auth[7:]
        try:
            token = ResearchAPIToken.objects.select_related('researcher').get(
                token=token_str, is_active=True
            )
        except ResearchAPIToken.DoesNotExist:
            raise AuthenticationFailed('Invalid or inactive API token.')
        # Update last_used asynchronously (best-effort; non-blocking)
        from django.utils import timezone
        ResearchAPIToken.objects.filter(pk=token.pk).update(last_used=timezone.now())
        return (token.researcher, token)
```

**Serializers** (`research/serializers.py`):

```python
class SessionSerializer(serializers.Serializer):
    session_key   = serializers.UUIDField()
    game_slug     = serializers.CharField(source='game.slug')
    game_name     = serializers.CharField(source='game.name')
    owner         = serializers.CharField(source='owner.username')
    status        = serializers.CharField()
    started_at    = serializers.DateTimeField()
    ended_at      = serializers.DateTimeField()
    summary       = serializers.JSONField(source='summary_json')

class PlayThroughSerializer(serializers.Serializer):
    playthrough_id = serializers.UUIDField()
    session_key    = serializers.UUIDField()
    game_slug      = serializers.CharField()
    started_at     = serializers.DateTimeField()
    ended_at       = serializers.DateTimeField()
    outcome        = serializers.CharField()
    step_count     = serializers.IntegerField()
    log_url        = serializers.SerializerMethodField()
    export_url     = serializers.SerializerMethodField()

    def get_log_url(self, obj):
        return f"/api/v1/sessions/{obj.session_key}/playthroughs/{obj.playthrough_id}/log/"

    def get_export_url(self, obj):
        return f"/api/v1/sessions/{obj.session_key}/playthroughs/{obj.playthrough_id}/log.jsonl"
```

**API views** (`research/api_views.py`):

| URL | View | Returns |
|---|---|---|
| `GET /api/v1/sessions/` | `APISessionListView` | Paginated list of `GameSession` (filter: game, status, date) |
| `GET /api/v1/sessions/<key>/` | `APISessionDetailView` | Single session + playthrough count |
| `GET /api/v1/sessions/<key>/playthroughs/` | `APIPlayThroughListView` | All play-throughs for session |
| `GET /api/v1/sessions/<key>/playthroughs/<pt_id>/` | `APIPlayThroughDetailView` | Single play-through |
| `GET /api/v1/sessions/<key>/playthroughs/<pt_id>/log/` | `APILogView` | Parsed log as JSON array |
| `GET /api/v1/sessions/<key>/playthroughs/<pt_id>/log.jsonl` | `APILogRawView` | Raw JSONL file stream |

**Example API usage from Jupyter:**
```python
import requests, pandas as pd

BASE = "https://portal.example.edu"
TOKEN = "your-uuid-token-here"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# List all sessions for game "tic-tac-toe"
sessions = requests.get(f"{BASE}/api/v1/sessions/?game=tic-tac-toe", headers=HEADERS).json()

# Get all log events for one play-through
pt_id = sessions['results'][0]['session_key']
log = requests.get(f"{BASE}/api/v1/sessions/{pt_id}/playthroughs/", headers=HEADERS).json()
```

A brief code snippet like the above should be displayed on the researcher's API token page as a "Quick Start" guide.

---

## 5. Navigation and Permission Wiring

**Access control:** All research views require `request.user.can_access_research()`. The existing `WSZUser.can_access_research()` method returns True for `ADMIN_RESEARCH` and `ADMIN_GENERAL`. Non-research users get a 403.

**Navigation integration:** The main `base.html` navigation bar already has a "Research" link placeholder (or should have one added). Add it as a nav item visible only when `user.can_access_research()`.

**URL prefix:** All research URLs are already registered under `/research/` via the main `urls.py`. The API URLs `/api/v1/` need to be added to the main `urls.py`:

```python
# wsz6_portal/urls.py — add:
path('api/v1/', include('wsz6_admin.research.api_urls')),
```

---

## 6. File Changes Summary

| File | Action | Notes |
|---|---|---|
| `wsz6_admin/research/models.py` | **Create** | `ResearchAnnotation`, `ResearchAPIToken` |
| `wsz6_admin/research/migrations/0001_initial.py` | **Create** | Auto-generated |
| `wsz6_admin/research/views.py` | **Replace stub** | All HTML-serving views |
| `wsz6_admin/research/api_views.py` | **Create** | DRF ViewSets / APIViews |
| `wsz6_admin/research/api_auth.py` | **Create** | Token authentication class |
| `wsz6_admin/research/serializers.py` | **Create** | DRF serializers |
| `wsz6_admin/research/urls.py` | **Extend** | Add all new URL patterns |
| `wsz6_admin/research/api_urls.py` | **Create** | API-only URL patterns |
| `wsz6_play/persistence/gdm_writer.py` | **Extend** | `write_artifact()`, `write_artifact_event()` |
| `templates/research/dashboard.html` | **Replace stub** | Session list with filters |
| `templates/research/session_detail.html` | **Create** | Session + playthrough list |
| `templates/research/log_viewer.html` | **Create** | Step-by-step log display |
| `templates/research/artifact_viewer.html` | **Create** | Document content pane |
| `templates/research/annotations.html` | **Create** | Annotation list/management |
| `templates/research/api_token.html` | **Create** | Token management + Quick Start |
| `wsz6_portal/urls.py` | **Extend** | Add `api/v1/` prefix |

---

## 7. Milestone Sequence and Dependencies

```
R1 Session List Dashboard
    │
    ├──▶ R2 Session Detail          (depends on R1)
    │         │
    │         └──▶ R3 Log Viewer    (depends on R2)
    │                   │
    │                   └──▶ R6 Annotations UI    (depends on R3)
    │
    ├──▶ R4 Artifact Support        (independent; extends GDM writer)
    │         │
    │         └──▶ (integrated into R3 log viewer)
    │
    ├──▶ R5 Export Endpoints        (depends on R2; independent of R3)
    │
    └──▶ R7 External API            (depends on R1 + R2; independent of R3–R6)
```

Recommended implementation order: **R1 → R2 → R4 → R3 → R5 → R6 → R7**

R4 (artifact infrastructure) is done early so the GDMWriter is ready for any games that produce artifacts; the log viewer (R3) then renders artifact events correctly on first implementation rather than requiring a retroactive update.

---

## 8. Open Questions Deferred

1. **Shared annotations:** The current plan makes annotations private to each researcher. If a future requirement arises for shared annotation (e.g., two researchers annotating the same session collaboratively), the `ResearchAnnotation` model can be extended with a `visibility` field (`private` / `shared`). No change to the database schema is needed now; the field can be added later.

2. **Vis rendering in log viewer:** The log viewer currently shows raw state JSON in a collapsible block. A future enhancement would call the game's vis module server-side to generate an HTML thumbnail for each step. This requires the vis module to be loadable from the research view context (it can be, since the game files are on disk). Left for a Phase 5 extension.

3. **Full-text search over log events:** The current log viewer paginates by frame number. A search box that filters frames by operator name, role, or keywords in state fields would be useful. This could be implemented as a client-side JavaScript filter over the page's rendered content, or as a server-side search using Python string matching. Deferred.

4. **Aggregate analytics views:** The DEV_PLAN mentions integration with Grafana and Jupyter. The REST API (R7) is the foundation for this. A pre-built Jupyter notebook template showing common analysis patterns (operator frequency, session duration distributions, goal-reach rate) could be provided as a downloadable resource from the portal. Deferred.

5. **GDM database access for non-`gdm` routing:** The current `PlayThrough` queries use `.using('gdm')`. If the research app is ever extracted to a separate service, this direct cross-database query breaks. For now, it is acceptable (same process, same server). The Phase-7 upgrade path (documented in `session_sync.py`) applies here too.

---

## 9. Milestone Completion Criteria

| Milestone | Done when... |
|---|---|
| **R1** | Research admin can log in, navigate to `/research/`, and see a paginated, filterable list of all game sessions. |
| **R2** | Clicking any session opens a detail page showing metadata and all play-throughs. |
| **R3** | Clicking "View Log" for a play-through shows all log events in chronological order, with collapsible state JSON and frame-level annotation capability. |
| **R4** | `GDMWriter.write_artifact()` is implemented; log viewer renders `artifact_saved` events with a working link to the artifact content. |
| **R5** | "Export JSONL" and "Export ZIP" buttons work; downloaded files are complete and valid. |
| **R6** | Researcher can add, view, and delete annotations at session, play-through, and frame levels. Annotations persist across sessions and are not visible to other users. |
| **R7** | `GET /api/v1/sessions/` returns valid JSON with Bearer token auth. A researcher can reproduce the Quick Start Jupyter example from the API token page. |
