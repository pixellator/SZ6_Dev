# Plan: Role-Specific Visualizations in WSZ6-play

**Date:** 2026-02-20
**Author:** S. Tanimoto (plan written with Claude Sonnet 4.6)

---

## Context

Games like OCCLUEdo (and Poker, etc.) require each player to see a different
visualization of the same game state — e.g., only their own card hand, not
opponents'. Currently `GameRunner.build_state_payload()` calls
`vis_module.render_state(state)` with no role information, then broadcasts the
identical `vis_html` to all connected players. This plan extends the engine so
that each player receives a visualization rendered for their specific role.

---

## Architecture Decision

Follow the **same pattern already used for operator filtering**: the broadcast
sends a *base payload* (no `vis_html`); each `GameConsumer` adds its own
role-specific `vis_html` before forwarding to its client.

Key facts from the codebase:

- `GameRunner._broadcast_state()` → `build_state_payload()` →
  `vis_module.render_state(state)` (no role, identical for all clients)
- `GameConsumer.state_update(event)` already filters operators per
  `self.role_num` (lines 351-353 of `game_consumer.py`) — vis rendering
  must mirror this pattern
- `GameConsumer.connect()` (line 87) stores `self.role_num` from the
  player's role token; the runner is fetched from the session store at
  connect but not yet cached on `self`
- `goal_reached` broadcast events contain no `vis_html` (only `type`,
  `step`, `goal_message`) — no changes needed there
- VIS modules that have no concept of roles work fine today and must
  continue to work without changes after this refactor

---

## Files to Change

| File | Change |
|---|---|
| `wsz6_play/engine/game_runner.py` | Add `render_vis_for_role()`, split `build_state_payload()` into base + vis parts, update `_broadcast_state()` |
| `wsz6_play/consumers/game_consumer.py` | Cache `self.runner` at connect; call `render_vis_for_role()` in both `connect()` and `state_update()` |
| `Vis-Features-Dev/game_sources/OCCLUEdo_WSZ6_VIS.py` | Update `render_state(state, role_num=None)` to show the correct player's hand |
| re-run `install_test_game` | Push updated VIS to `games_repo/occluedo/` |

---

## Step-by-Step Changes

### Step 1 — `wsz6_play/engine/game_runner.py`

**1a. Add `import inspect`** near the top of the file (alongside `import asyncio`).

**1b. Add `render_vis_for_role()` method** on `GameRunner`:

```python
async def render_vis_for_role(self, state, role_num=None):
    """Render vis_html for a specific viewing role.

    Calls vis_module.render_state(state, role_num=role_num) when the
    VIS module's render_state accepts a role_num keyword argument;
    otherwise calls render_state(state) for backward compatibility with
    existing VIS modules that have no role concept.

    Returns None if no vis module is loaded or rendering raises.
    """
    vis_module = getattr(self.formulation, 'vis_module', None)
    if vis_module is None or not callable(getattr(vis_module, 'render_state', None)):
        return None
    try:
        sig = inspect.signature(vis_module.render_state)
        if 'role_num' in sig.parameters:
            return await asyncio.to_thread(
                vis_module.render_state, state, role_num
            )
        else:
            return await asyncio.to_thread(vis_module.render_state, state)
    except Exception:
        logger.exception("render_vis_for_role() failed at step %s", self.step)
        return None
```

**1c. Extract `_build_base_payload()` from `build_state_payload()`.**

Everything in the current `build_state_payload()` *except* the vis rendering
is synchronous and can become a plain (non-async) helper:

```python
def _build_base_payload(self) -> dict:
    """Return state_update dict without vis_html (synchronous)."""
    state    = self.current_state
    ops_info = self.get_ops_info(state)
    try:
        at_goal = state.is_goal()
    except Exception:
        at_goal = False
    return {
        'type':             'state_update',
        'step':             self.step,
        'state':            serialize_state(state),
        'state_text':       str(state),
        'is_goal':          at_goal,
        'is_parallel':      getattr(state, 'parallel', False),
        'operators':        ops_info,
        'current_role_num': getattr(state, 'current_role_num', 0),
    }
```

**1d. Rewrite `build_state_payload(role_num=None)`** to delegate:

```python
async def build_state_payload(self, role_num=None) -> dict:
    """Build a complete state_update payload for a specific role."""
    payload  = self._build_base_payload()
    vis_html = await self.render_vis_for_role(self.current_state, role_num)
    if vis_html is not None:
        payload['vis_html'] = vis_html
    return payload
```

**1e. Change `_broadcast_state()`** to broadcast WITHOUT vis_html (each
consumer renders its own):

```python
async def _broadcast_state(self) -> None:
    payload = self._build_base_payload()  # synchronous; no vis rendering
    await self.broadcast(payload)
```

---

### Step 2 — `wsz6_play/consumers/game_consumer.py`

**2a. Cache runner in `connect()`** (after the runner is fetched, around line 99):

```python
self.runner = runner
```

**2b. Pass `role_num` to `build_state_payload()` in `connect()`** (line 102):

```python
payload = await runner.build_state_payload(role_num=self.role_num)
# (was: await runner.build_state_payload())
```

**2c. Replace `state_update(self, event)`** (lines 351-353) with:

```python
async def state_update(self, event):
    filtered = _filter_ops_for_role(event.get('operators', []), self.role_num)
    out = {**event, 'operators': filtered, 'your_role_num': self.role_num}

    vis_html = await self.runner.render_vis_for_role(
        self.runner.current_state, self.role_num
    )
    if vis_html is not None:
        out['vis_html'] = vis_html
    else:
        out.pop('vis_html', None)   # don't send stale/absent vis_html

    await self.send_json(out)
```

> **Thread-safety note:** `self.runner.current_state` is safe here because
> Django Channels runs on a single asyncio event loop. A new `apply_operator`
> cannot interleave with this handler mid-execution.

---

### Step 3 — `Vis-Features-Dev/game_sources/OCCLUEdo_WSZ6_VIS.py`

**Change the `render_state` signature:**

```python
# OLD
def render_state(state) -> str:

# NEW
def render_state(state, role_num=None) -> str:
```

**Inside `render_state`, replace the variable used to decide whose card hand
to display:**

```python
viewing_role = role_num if role_num is not None else state.current_role_num
```

Use `viewing_role` (instead of `state.current_role_num`) when selecting which
player's hand cards are rendered in the card-hand strip at the bottom of the
layout.

The room map, action panel (whose content depends on `state.suggestion_phase`
and `state.whose_turn`), and status bar remain based on game `state` attributes
and are unchanged — they represent the shared, public game view.

**Observer role:** When `viewing_role` equals the observer role number (6),
show an empty hand strip (or a "Observer — no hand" label).

---

### Step 4 — Reinstall OCCLUEdo

```bash
cd wsz6_portal
source .venv/bin/activate
DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development \
    python manage.py install_test_game
```

---

## Backward Compatibility

| VIS module | `render_state` signature | Engine behavior after change |
|---|---|---|
| Tic-Tac-Toe, Mt. Rainier, Click-Word, Pixel-Probe | `def render_state(state)` | `inspect.signature` finds no `role_num` param → called as before |
| OCCLUEdo (updated) | `def render_state(state, role_num=None)` | Called with the viewing player's `role_num`; defaults gracefully when `None` |
| Future role-aware games | `def render_state(state, role_num=None)` | Full role-private rendering |

All existing single-player and symmetric-display games require **no changes**.

---

## Verification

1. **Regression — Tic-Tac-Toe**: Play a full TTT session; confirm vis renders
   normally for both players (existing VIS path unchanged).

2. **Role-specific — OCCLUEdo**:
   - Log in as two users in separate browser windows.
   - Assign Miss Scarlet (role 0) to player 1, Mr. Green (role 1) to player 2.
   - Start game. Verify player 1's card-hand strip shows Miss Scarlet's cards;
     player 2's strip shows Mr. Green's cards.
   - Apply an operator and verify both browsers update with correct
     role-private hands.

3. **Observer**: Join as observer (role 6); verify no private hand is shown.

4. **Reconnect**: Close and reopen a browser tab; verify the reconnected
   player receives the correct role-specific vis on the initial connect.
