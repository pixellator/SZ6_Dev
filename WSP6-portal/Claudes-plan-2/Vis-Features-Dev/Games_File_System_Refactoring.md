# Games File-System Refactoring Plan

**Date:** 2026-02-20
**Author:** Claude Sonnet 4.6
**Addresses:** Problems 1–5 from `Claudes_Audit_of_WSZ6_portal_Feb_20_2026.md`, Part III

---

## Overview

Five interrelated problems affect the current game file organisation:

| # | Problem | Root cause |
|---|---------|------------|
| 1 | Game sources split across `Textual_SZ6/` and `Vis-Features-Dev/game_sources/` | Accidental; no canonical home |
| 2 | `soluzion6_02.py` copied into every installed game directory (~11 copies) | `pff_loader` adds the game dir to `sys.path`; base lib must be there |
| 3 | No enforced structure within a game directory; vis files sit next to PFFs with no manifest | No install-time metadata written |
| 4 | Two catalog entries (`tic-tac-toe`, `tic-tac-toe-vis`) for one logical game | Vis requires a wrapper PFF that explicitly imports the vis module |
| 5 | No canonical `game_asset_url()` helper; vis files hard-code URL pattern | Helper never implemented |

All five are addressed together because they are interdependent: solving Problem 2 changes the `pff_loader`, solving Problem 4 requires adding auto-discovery to that same loader, and solving Problem 1 requires restructuring `install_test_game.py` which also drives Problem 3 (the metadata manifest).

---

## Current State (before changes)

```
SZ6_Dev/
├── Textual_SZ6/               ← shared base lib + most game PFFs (source)
│   ├── soluzion6_02.py        ← single source of truth for base library
│   ├── Tic_Tac_Toe_SZ6.py
│   ├── Tic_Tac_Toe_SZ6_with_vis.py   ← wrapper PFF (only exists to import vis)
│   ├── Tic_Tac_Toe_WSZ6_VIS.py
│   ├── Missionaries_SZ6.py
│   ├── Guess_My_Age_SZ6.py
│   ├── Rock_Paper_Scissors_SZ6.py
│   ├── Remote_LLM_Test_Game_SZ6.py
│   └── Trivial_Writing_Game_SZ6.py
│
├── WSP6-portal/Claudes-plan-2/Vis-Features-Dev/game_sources/  ← newer games (source)
│   ├── Show_Mt_Rainier_SZ6.py / _WSZ6_VIS.py / _images/
│   ├── Click_Word_SZ6.py / _WSZ6_VIS.py
│   ├── Pixel_Probe_SZ6.py / _WSZ6_VIS.py / UW_Aerial_images/
│   ├── OCCLUEdo_SZ6.py / _WSZ6_VIS.py / OCCLUEdo_images/
│   └── ...
│
└── games_repo/                ← installed runtime copies
    ├── tic-tac-toe/
    │   ├── Tic_Tac_Toe_SZ6.py
    │   └── soluzion6_02.py    ← copy #1
    ├── tic-tac-toe-vis/
    │   ├── Tic_Tac_Toe_SZ6_with_vis.py
    │   ├── Tic_Tac_Toe_WSZ6_VIS.py
    │   └── soluzion6_02.py    ← copy #2
    ├── missionaries/
    │   ├── Missionaries_SZ6.py
    │   └── soluzion6_02.py    ← copy #3
    ... (8 more game dirs, each with a soluzion6_02.py copy)
```

---

## Target State (after changes)

```
SZ6_Dev/
├── Textual_SZ6/               ← textual engine only; no web game files remain here
│   ├── soluzion6_02.py        ← single source of truth (unchanged)
│   └── Textual_SOLUZION6.py  (other textual tools, untouched)
│
├── game_sources/              ← NEW: canonical home for all authored game files
│   ├── tic_tac_toe/
│   │   ├── Tic_Tac_Toe_SZ6.py
│   │   └── Tic_Tac_Toe_WSZ6_VIS.py
│   ├── missionaries/
│   │   └── Missionaries_SZ6.py
│   ├── guess_my_age/
│   │   └── Guess_My_Age_SZ6.py
│   ├── rock_paper_scissors/
│   │   └── Rock_Paper_Scissors_SZ6.py
│   ├── remote_llm_test/
│   │   └── Remote_LLM_Test_Game_SZ6.py
│   ├── trivial_writing_game/
│   │   └── Trivial_Writing_Game_SZ6.py
│   ├── show_mt_rainier/
│   │   ├── Show_Mt_Rainier_SZ6.py
│   │   ├── Show_Mt_Rainier_WSZ6_VIS.py
│   │   └── Show_Mt_Rainier_images/
│   ├── click_the_word/
│   │   ├── Click_Word_SZ6.py
│   │   └── Click_Word_WSZ6_VIS.py
│   ├── pixel_uw_aerial/
│   │   ├── Pixel_Probe_SZ6.py
│   │   ├── Pixel_Probe_WSZ6_VIS.py
│   │   └── UW_Aerial_images/
│   └── occluedo/
│       ├── OCCLUEdo_SZ6.py
│       ├── OCCLUEdo_WSZ6_VIS.py
│       └── OCCLUEdo_images/
│
└── games_repo/                ← installed runtime copies (generated; git-ignored)
    ├── tic-tac-toe/
    │   ├── Tic_Tac_Toe_SZ6.py
    │   ├── Tic_Tac_Toe_WSZ6_VIS.py   ← auto-discovered at runtime
    │   └── metadata.json
    ├── missionaries/
    │   ├── Missionaries_SZ6.py
    │   └── metadata.json
    ... (no soluzion6_02.py copies; no tic-tac-toe-vis directory)
```

`Textual_SZ6/` remains on `sys.path` via `pff_loader`, so `from soluzion6_02 import ...` continues to work in every PFF without any per-game copy.

---

## Step-by-Step Implementation

---

### Step 1 — Create `SZ6_Dev/game_sources/` source tree  *(filesystem only)*

**What to do:**

1. Create the directory `SZ6_Dev/game_sources/` and the ten game subdirectories listed below.
2. Copy (do not move — sources in `Textual_SZ6/` and `Vis-Features-Dev/game_sources/` remain as-is; we only *copy* so nothing breaks before Step 6):

| Source subdirectory | Files to copy | From |
|---|---|---|
| `game_sources/tic_tac_toe/` | `Tic_Tac_Toe_SZ6.py`, `Tic_Tac_Toe_WSZ6_VIS.py` | `Textual_SZ6/` |
| `game_sources/missionaries/` | `Missionaries_SZ6.py` | `Textual_SZ6/` |
| `game_sources/guess_my_age/` | `Guess_My_Age_SZ6.py` | `Textual_SZ6/` |
| `game_sources/rock_paper_scissors/` | `Rock_Paper_Scissors_SZ6.py` | `Textual_SZ6/` |
| `game_sources/remote_llm_test/` | `Remote_LLM_Test_Game_SZ6.py` | `Textual_SZ6/` |
| `game_sources/trivial_writing_game/` | `Trivial_Writing_Game_SZ6.py` | `Textual_SZ6/` |
| `game_sources/show_mt_rainier/` | `Show_Mt_Rainier_SZ6.py`, `Show_Mt_Rainier_WSZ6_VIS.py`, `Show_Mt_Rainier_images/` | `Vis-Features-Dev/game_sources/` |
| `game_sources/click_the_word/` | `Click_Word_SZ6.py`, `Click_Word_WSZ6_VIS.py` | `Vis-Features-Dev/game_sources/` |
| `game_sources/pixel_uw_aerial/` | `Pixel_Probe_SZ6.py`, `Pixel_Probe_WSZ6_VIS.py`, `UW_Aerial_images/` | `Vis-Features-Dev/game_sources/` |
| `game_sources/occluedo/` | `OCCLUEdo_SZ6.py`, `OCCLUEdo_WSZ6_VIS.py`, `OCCLUEdo_images/` | `Vis-Features-Dev/game_sources/` |

**Note:** Do NOT copy `Tic_Tac_Toe_SZ6_with_vis.py` — this wrapper file becomes obsolete in Step 5 and is not carried forward.
**Note:** Do NOT copy `soluzion6_02.py` — it stays only in `Textual_SZ6/`.

**Verify:**
```bash
ls SZ6_Dev/game_sources/tic_tac_toe/
# → Tic_Tac_Toe_SZ6.py  Tic_Tac_Toe_WSZ6_VIS.py
```

---

### Step 2 — Add `SOLUZION_LIB_DIR` to `settings/base.py`  *(Problem 2 — settings)*

**File:** `wsz6_portal/wsz6_portal/settings/base.py`

After the existing `GAMES_REPO_ROOT` block, add:

```python
# Directory containing the shared SOLUZION6 base library (soluzion6_02.py).
# Added to sys.path by pff_loader so PFFs can import it without a per-game copy.
SOLUZION_LIB_DIR = config(
    'SOLUZION_LIB_DIR',
    default=str(BASE_DIR.parent.parent.parent / 'Textual_SZ6')
)
```

This is environment-overridable via `.env` so a production deployment can point to a different location (or a future installed package).

---

### Step 3 — Update `pff_loader.py`  *(Problems 2, 3, 4)*

**File:** `wsz6_portal/wsz6_play/engine/pff_loader.py`

Three changes:

#### 3a — Add `SOLUZION_LIB_DIR` to `sys.path` in `load_formulation()` (Problem 2)

At the top of `load_formulation()`, before the game directory is added to `sys.path`:

```python
from django.conf import settings

def load_formulation(game_slug: str, games_repo_root: str):
    game_dir = os.path.join(games_repo_root, game_slug)
    pff_path = _find_pff_file(game_dir, game_slug)

    # Add the shared SOLUZION6 base library directory so PFFs can
    # `from soluzion6_02 import ...` without a per-game copy of that file.
    shared_lib = getattr(settings, 'SOLUZION_LIB_DIR', None)
    if shared_lib and os.path.isdir(shared_lib) and shared_lib not in sys.path:
        sys.path.insert(0, shared_lib)

    # Game directory second (after shared lib) so game-local modules shadow
    # shared lib names only when intentional.
    if game_dir not in sys.path:
        sys.path.insert(0, game_dir)
    ...
```

#### 3b — Exclude `*_WSZ6_VIS.py` from the PFF fallback scan in `_find_pff_file()` (Problem 3/4)

Update the fallback scan to exclude vis files, preventing the loader from accidentally picking up a vis module as the PFF:

```python
def _find_pff_file(game_dir: str, game_slug: str) -> str:
    ...
    # Fallback: scan directory, excluding vis modules and __init__.py.
    try:
        py_files = sorted(
            f for f in os.listdir(game_dir)
            if f.endswith('.py')
            and f != '__init__.py'
            and not f.endswith('_WSZ6_VIS.py')   # ← NEW: skip vis modules
        )
    ...
```

#### 3c — Add `load_vis_module(game_dir)` function (Problem 4)

Add a new public function below `unload_formulation()`:

```python
def load_vis_module(game_dir: str):
    """Auto-discover and load a vis module from the game directory.

    Looks for exactly one file matching ``*_WSZ6_VIS.py`` in ``game_dir``.
    If exactly one is found, imports and returns it as a module object.
    Returns None if none are found; logs a warning if multiple are found.

    The returned module is loaded into sys.modules under a unique name so
    multiple concurrent sessions each get their own independent module state.
    """
    try:
        vis_files = [
            f for f in os.listdir(game_dir)
            if f.endswith('_WSZ6_VIS.py')
        ]
    except FileNotFoundError:
        return None

    if not vis_files:
        return None
    if len(vis_files) > 1:
        logger.warning(
            "Multiple _WSZ6_VIS.py files found in %s: %s — skipping auto-discovery.",
            game_dir, vis_files
        )
        return None

    vis_path    = os.path.join(game_dir, vis_files[0])
    unique_name = f"_vis_{uuid.uuid4().hex}"
    try:
        spec = importlib.util.spec_from_file_location(unique_name, vis_path)
        if spec is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module
        spec.loader.exec_module(module)
        logger.debug("Auto-loaded vis module: %s → %s", vis_files[0], unique_name)
        return module
    except Exception as exc:
        sys.modules.pop(unique_name, None)
        logger.warning("Failed to load vis module %s: %s", vis_path, exc)
        return None
```

---

### Step 4 — Update `game_runner.py`  *(Problem 5)*

**File:** `wsz6_portal/wsz6_play/engine/game_runner.py`

#### 4a — Accept `game_slug` in `__init__`

```python
class GameRunner:
    def __init__(
        self,
        formulation,
        role_manager,
        broadcast_func: Callable[..., Coroutine],
        game_slug: str = '',          # ← NEW
    ):
        self.formulation  = formulation
        self.role_manager = role_manager
        self.broadcast    = broadcast_func
        self.game_slug    = game_slug  # ← NEW: used to build asset base_url
        ...
```

#### 4b — Pass `base_url` to `render_vis_for_role()` when accepted (Problem 5)

In `render_vis_for_role()`, add detection of the `base_url` parameter alongside the existing `role_num` / `instance_data` detection:

```python
async def render_vis_for_role(self, state, role_num=None):
    vis_module = getattr(self.formulation, 'vis_module', None)
    if vis_module is None or not callable(getattr(vis_module, 'render_state', None)):
        return None
    try:
        sig    = inspect.signature(vis_module.render_state)
        params = sig.parameters
        kwargs = {}
        if 'role_num' in params:
            kwargs['role_num'] = role_num
        if 'instance_data' in params:
            kwargs['instance_data'] = getattr(self.formulation, 'instance_data', None)
        if 'base_url' in params:                                        # ← NEW
            kwargs['base_url'] = f"/play/game-asset/{self.game_slug}/" # ← NEW
        return await asyncio.to_thread(vis_module.render_state, state, **kwargs)
    except Exception:
        logger.exception("render_vis_for_role() failed at step %s", self.step)
        return None
```

**Convention for vis authors:** Declare `base_url=''` as a keyword argument in `render_state` to receive the asset base URL automatically:

```python
# In a *_WSZ6_VIS.py file:
def render_state(state, role_num=0, instance_data=None, base_url=''):
    img_src = base_url + 'my_image.png'   # correct, portable
    ...
```

Vis files that do not declare `base_url` continue to work unchanged (backward compatible).

---

### Step 5 — Update `lobby_consumer.py`  *(Problem 4)*

**File:** `wsz6_portal/wsz6_play/consumers/lobby_consumer.py`

#### 5a — Import `load_vis_module`

```python
from wsz6_play.engine.pff_loader import PFFLoadError, load_formulation, load_vis_module
```

#### 5b — Auto-discover vis in `_handle_start_game()` and `_resume_from_checkpoint()`

After the `load_formulation()` call in both methods, insert:

```python
# Auto-discover a vis module if the PFF did not explicitly set one.
if getattr(formulation, 'vis_module', None) is None:
    game_dir = os.path.join(settings.GAMES_REPO_ROOT, session['game_slug'])
    vis_mod  = await asyncio.to_thread(load_vis_module, game_dir)
    if vis_mod is not None:
        formulation.vis_module = vis_mod
```

Add `import os` at the top of the file if not already present.

#### 5c — Pass `game_slug` to `_make_runner_and_bots()`

Update `_make_runner_and_bots()` to accept and pass through `game_slug`:

```python
def _make_runner_and_bots(self, formulation, rm, session_key, game_slug='') -> tuple:
    game_group    = f"game_{session_key}"
    channel_layer = get_channel_layer()

    async def broadcast(payload: dict):
        await channel_layer.group_send(game_group, payload)

    runner = GameRunner(formulation, rm, broadcast, game_slug=game_slug)
    ...
```

And update every call site (`_handle_start_game`, `_resume_from_checkpoint`):

```python
runner, bots = self._make_runner_and_bots(
    formulation, rm, self.session_key,
    game_slug=session['game_slug'],   # ← NEW
)
```

---

### Step 6 — Update `install_test_game.py`  *(Problems 1, 2, 3, 4)*

**File:** `wsz6_portal/wsz6_admin/games_catalog/management/commands/install_test_game.py`

This is the most extensive rewrite of the management command.

#### 6a — Change source root and remove `source_dir` override

Replace the current dual-root logic (`textual_dir` + `source_dir` per game) with a single canonical root:

```python
GAME_SOURCES_ROOT = settings.BASE_DIR.parent.parent.parent / 'game_sources'
```

Each game is sourced from `GAME_SOURCES_ROOT / gdef['source_subdir']`.

#### 6b — New `GAME_DEFS` (removes `tic-tac-toe-vis`; removes `source_dir`; adds `source_subdir`)

```python
GAME_DEFS = [
    {
        'slug':          'tic-tac-toe',
        'name':          'Tic-Tac-Toe',
        'source_subdir': 'tic_tac_toe',
        'pff_file':      'Tic_Tac_Toe_SZ6.py',
        'vis_file':      'Tic_Tac_Toe_WSZ6_VIS.py',
        'brief_desc':    '...',
        'min_players':   2,
        'max_players':   27,
    },
    {
        'slug':          'missionaries',
        'name':          'Missionaries and Cannibals',
        'source_subdir': 'missionaries',
        'pff_file':      'Missionaries_SZ6.py',
        'brief_desc':    '...',
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'guess-my-age',
        'name':          'Guess My Age',
        'source_subdir': 'guess_my_age',
        'pff_file':      'Guess_My_Age_SZ6.py',
        'brief_desc':    '...',
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'rock-paper-scissors',
        'name':          'Rock-Paper-Scissors',
        'source_subdir': 'rock_paper_scissors',
        'pff_file':      'Rock_Paper_Scissors_SZ6.py',
        'brief_desc':    '...',
        'min_players':   2,
        'max_players':   2,
    },
    {
        'slug':          'remote-llm-test',
        'name':          'Remote LLM Test Game',
        'source_subdir': 'remote_llm_test',
        'pff_file':      'Remote_LLM_Test_Game_SZ6.py',
        'brief_desc':    '...',
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'trivial-writing-game',
        'name':          'Trivial Writing Game',
        'source_subdir': 'trivial_writing_game',
        'pff_file':      'Trivial_Writing_Game_SZ6.py',
        'brief_desc':    '...',
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'show-mt-rainier',
        'name':          'Mt. Rainier Views',
        'source_subdir': 'show_mt_rainier',
        'pff_file':      'Show_Mt_Rainier_SZ6.py',
        'vis_file':      'Show_Mt_Rainier_WSZ6_VIS.py',
        'images_dir':    'Show_Mt_Rainier_images',
        'brief_desc':    '...',
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'click-the-word',
        'name':          "Cliquez sur l'image",
        'source_subdir': 'click_the_word',
        'pff_file':      'Click_Word_SZ6.py',
        'vis_file':      'Click_Word_WSZ6_VIS.py',
        'brief_desc':    '...',
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'pixel-uw-aerial',
        'name':          'Pixel Values with Old UW Aerial Image',
        'source_subdir': 'pixel_uw_aerial',
        'pff_file':      'Pixel_Probe_SZ6.py',
        'vis_file':      'Pixel_Probe_WSZ6_VIS.py',
        'images_dir':    'UW_Aerial_images',
        'brief_desc':    '...',
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'occluedo',
        'name':          'OCCLUEdo: An Occluded Game of Clue',
        'source_subdir': 'occluedo',
        'pff_file':      'OCCLUEdo_SZ6.py',
        'vis_file':      'OCCLUEdo_WSZ6_VIS.py',
        'images_dir':    'OCCLUEdo_images',
        'brief_desc':    '...',
        'min_players':   2,
        'max_players':   7,
    },
]
```

(Keep existing `brief_desc` strings verbatim from the current `GAME_DEFS`.)

#### 6c — Remove `soluzion6_02.py` copying in `handle()`

Remove the block that locates and copies `src_base`:

```python
# REMOVE these lines from handle():
src_base = textual_dir / 'soluzion6_02.py'
if not src_base.exists():
    raise CommandError(f"Base module not found: {src_base}")
```

Update `_install_game()` signature to remove the `src_base` parameter and remove the line:

```python
shutil.copy2(src_base, dest_dir / src_base.name)  # ← DELETE
```

#### 6d — Update `handle()` to use the new source root

```python
game_sources = settings.BASE_DIR.parent.parent.parent / 'game_sources'
if not game_sources.is_dir():
    raise CommandError(
        f"game_sources directory not found at {game_sources}. "
        "Run Step 1 of Games_File_System_Refactoring.md first."
    )

for gdef in GAME_DEFS:
    src_dir = game_sources / gdef['source_subdir']
    ok = self._install_game(gdef, src_dir, games_repo, owner, status, Game)
    ...
```

#### 6e — Write `metadata.json` at install time (Problem 3)

At the end of `_install_game()`, after creating/updating the `Game` record, write:

```python
import json, datetime

vis_file = gdef.get('vis_file', '')
metadata = {
    'slug':         slug,
    'name':         name,
    'version':      '1.0',
    'min_players':  gdef['min_players'],
    'max_players':  gdef['max_players'],
    'pff_file':     pff_file,
    'vis_file':     vis_file,
    'installed_at': datetime.datetime.utcnow().isoformat() + 'Z',
}
(dest_dir / 'metadata.json').write_text(
    json.dumps(metadata, indent=2), encoding='utf-8'
)
```

#### 6f — Delete the `tic-tac-toe-vis` Game record

After the install loop, add a cleanup step:

```python
# Remove the now-obsolete tic-tac-toe-vis catalog entry (collapsed into tic-tac-toe).
deleted, _ = Game.objects.filter(slug='tic-tac-toe-vis').delete()
if deleted:
    self.stdout.write(self.style.SUCCESS(
        "  DEL   Removed obsolete 'tic-tac-toe-vis' catalog entry."
    ))
```

This is idempotent (no-op if the record was already deleted).

---

### Step 7 — Rebuild `games_repo/` (runtime)

After all code changes are committed, rebuild the installed game directories:

```bash
cd wsz6_portal
source .venv/bin/activate
DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development \
    python manage.py install_test_game
```

This will:
- Install all 10 games from `SZ6_Dev/game_sources/`
- Write `metadata.json` into each game dir
- Copy vis files alongside PFFs (no `soluzion6_02.py` copied)
- Delete the `tic-tac-toe-vis` DB entry
- Recreate the `tic-tac-toe` dir with both `Tic_Tac_Toe_SZ6.py` and `Tic_Tac_Toe_WSZ6_VIS.py`

Then manually remove the old `tic-tac-toe-vis` game directory (the DB record will already be gone):

```bash
rm -rf SZ6_Dev/games_repo/tic-tac-toe-vis
```

And remove stale `soluzion6_02.py` copies from the other game directories:

```bash
for d in SZ6_Dev/games_repo/*/; do
    rm -f "$d/soluzion6_02.py"
done
```

(These `rm` operations are safe because after Step 3a, the loader adds `Textual_SZ6/` to `sys.path` first, making the per-game copies redundant.)

---

### Step 8 — (Optional) Update vis files to use `base_url`  *(Problem 5 — vis author side)*

This step is only needed if you want vis files to stop hard-coding the URL.  Existing vis files continue to work unchanged. For any vis file that uses hard-coded `/play/game-asset/<slug>/…` URLs, update its `render_state` signature:

```python
# Before:
def render_state(state, role_num=0, instance_data=None):
    src = f'/play/game-asset/occluedo/room_kitchen.png'
    ...

# After:
def render_state(state, role_num=0, instance_data=None, base_url=''):
    src = base_url + 'room_kitchen.png'
    ...
```

The `base_url` will be `/play/game-asset/<slug>/` injected by the runner automatically (Step 4b).

---

## File Change Summary

| File | Change type | Addresses |
|---|---|---|
| `SZ6_Dev/game_sources/` (new directory tree) | Create | Problem 1 |
| `wsz6_portal/settings/base.py` | Add `SOLUZION_LIB_DIR` | Problem 2 |
| `wsz6_play/engine/pff_loader.py` | Add shared lib to `sys.path`; exclude vis from PFF scan; add `load_vis_module()` | Problems 2, 3, 4 |
| `wsz6_play/engine/game_runner.py` | Add `game_slug` param; pass `base_url` | Problem 5 |
| `wsz6_play/consumers/lobby_consumer.py` | Call `load_vis_module()`; pass `game_slug` to runner | Problems 4, 5 |
| `wsz6_admin/.../install_test_game.py` | New source root; remove `soluzion6_02` copy; remove `tic-tac-toe-vis`; add `metadata.json` | Problems 1, 2, 3, 4 |
| `SZ6_Dev/games_repo/` | Rebuilt via `install_test_game`; stale copies cleaned up manually | Problems 2, 3, 4 |

---

## Risk and Compatibility Notes

- **Backward compatibility — PFF vis imports:** PFFs that already set `self.vis_module` (e.g. future PFFs that still use the explicit import pattern) continue to work. `load_vis_module()` is only called when `formulation.vis_module is None`. No existing PFF needs to be modified.
- **`tic-tac-toe` plain game:** After this change, `tic-tac-toe` will have SVG visualization (because `Tic_Tac_Toe_WSZ6_VIS.py` is in its directory and will be auto-discovered). If a text-only `tic-tac-toe` is ever needed again, rename the vis file away from the `*_WSZ6_VIS.py` pattern or add a `no_vis: True` flag to GAME_DEFS (not currently implemented, but straightforward to add).
- **Session store — in-flight games:** `install_test_game` rebuilds `games_repo/` directories. Any game session active during `install_test_game` may fail to find its PFF after the directory is recreated. This is a dev-only command and the server should be idle when it is run.
- **`soluzion6_02.py` removal timing:** After running `install_test_game`, the per-game copies in `games_repo/` can be removed. If `pff_loader.py` has NOT been updated yet (Step 3a), removing the copies will break games. Perform Steps 2–6 atomically (same server restart cycle) before running `install_test_game`.
- **`Tic_Tac_Toe_SZ6_with_vis.py`:** This file can be deleted from `Textual_SZ6/` once Step 7 confirms everything works. Leave it in place during testing as a safety net.

---

## Implementation Order

Execute in this order to avoid breaking the running system:

1. **Step 1** — Copy files into `game_sources/` (no code touched, zero risk)
2. **Steps 2–5** — Code changes (edit but don't restart yet)
3. **Step 6** — Update `install_test_game.py`
4. **Restart server** — Pick up new settings and code
5. **Step 7** — Run `install_test_game`; verify in browser
6. **Cleanup** — Remove `tic-tac-toe-vis/` directory and stale `soluzion6_02.py` copies
7. **Step 8** (optional) — Update vis files to use `base_url`
