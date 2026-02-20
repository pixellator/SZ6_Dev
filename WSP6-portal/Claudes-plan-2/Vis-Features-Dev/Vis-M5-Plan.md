# Vis-M5-Plan.md — Previous-State Toggle

**Date:** 2026-02-19
**Milestone:** M5 (Previous-State Toggle)
**Depends on:** M0–M4 complete (already committed)
**Status:** Ready to implement

---

## 1. Goal

Add a "Show Previous" toggle button that lets a player flip between the
current-state visualization and the immediately preceding state's
visualization.  The toggle must work in both normal view and full-screen
mode.

---

## 2. Current state analysis

### What already exists

| Component | Relevant state |
|---|---|
| `game.html` JS globals | `currentOps`, `fsActive`, `transitionHistory` — **no** `currentVisHtml` / `prevVisHtml` variables yet |
| `onStateUpdate()` | Sets `visDisplay.innerHTML = msg.vis_html` directly; does not save a copy before replacing |
| `#fs-overlay` | Has `#fs-close` (✕) and `#fs-op-tray` with `#fs-ops-list` — **no** prev-toggle button |
| `game_runner.build_state_payload()` | Sends `vis_html` for the current state; **does not** send a previous-state rendering |
| State stack | `game_runner.state_stack` holds the full history; `undo()` pops and rebroadcasts |

### Design decision: frontend-only, no backend change

The simplest correct approach is to cache `prevVisHtml` in the browser:

- On each `state_update`, save `currentVisHtml` → `prevVisHtml` before
  overwriting with the new `vis_html`.
- The toggle swaps `visDisplay.innerHTML` between the two cached strings.
- A new state_update from the server (any player's move) auto-reverts the
  toggle to "show current".
- No extra `render_state()` call on the backend; no protocol change.

This avoids rendering the previous state twice per move and keeps the
server stateless with respect to the toggle.

---

## 3. Implementation

Only **`game.html`** changes.  No changes to `game_runner.py`, consumers,
or any vis file.

### 3.1 New JS state variables

**Location:** insert after the existing globals block (currently ends near
the `transitionHistory` line, around line 325).

```javascript
// ── Previous-state toggle (M5) ────────────────────────────────────
let currentVisHtml = '';   // vis_html from the most recent state_update
let prevVisHtml    = '';   // vis_html from one step earlier ('' at step 0)
let showingPrev    = false; // true while the toggle is showing prev state
```

---

### 3.2 Modify `onStateUpdate()` to track previous vis HTML

**Location:** the `if (msg.vis_html)` branch (currently ~line 413).

Replace:

```javascript
    if (msg.vis_html) {
      visDisplay.innerHTML     = msg.vis_html;
      visDisplay.style.display = '';
      textDisplay.style.display = 'none';
      setupHitCanvas();
```

With:

```javascript
    if (msg.vis_html) {
      // M5: rotate vis cache before replacing
      prevVisHtml    = currentVisHtml;
      currentVisHtml = msg.vis_html;
      showingPrev    = false;              // new move → revert to current

      visDisplay.innerHTML      = msg.vis_html;
      visDisplay.classList.remove('showing-prev');
      visDisplay.style.display  = '';
      textDisplay.style.display = 'none';
      setupHitCanvas();
      _updatePrevToggle();
```

Also handle the text-only fallback branch (the `else` that sets
`textDisplay`): in that branch, also clear `currentVisHtml` and
`prevVisHtml` so the toggle stays disabled for text-only games:

```javascript
    } else {
      prevVisHtml    = currentVisHtml;
      currentVisHtml = '';
      showingPrev    = false;
      visDisplay.style.display  = 'none';
      textDisplay.style.display = '';
      textDisplay.textContent   = msg.state_text || '';
      _updatePrevToggle();
    }
```

---

### 3.3 Add `_updatePrevToggle()` helper function

Add this function alongside the other helper functions (e.g. near
`renderFsOps`):

```javascript
  function _updatePrevToggle() {
    const hasPrev = !!prevVisHtml;
    document.querySelectorAll('.prev-toggle-btn').forEach(btn => {
      btn.disabled   = !hasPrev;
      btn.textContent = showingPrev ? '\u21A9 Show Current' : '\u21D4 Show Previous';
    });
    const visDisplay = document.getElementById('vis-display');
    if (visDisplay) {
      visDisplay.classList.toggle('showing-prev', showingPrev);
    }
  }
```

`querySelectorAll('.prev-toggle-btn')` updates both the normal-view button
and the full-screen tray button in one call.

---

### 3.4 Add `togglePreviousState()` global function

```javascript
  window.togglePreviousState = function() {
    if (!prevVisHtml) return;
    showingPrev = !showingPrev;
    const visDisplay = document.getElementById('vis-display');
    visDisplay.innerHTML = showingPrev ? prevVisHtml : currentVisHtml;
    setupHitCanvas();          // re-parse Tier-2 canvas regions if present
    _updatePrevToggle();
  };
```

---

### 3.5 Add the normal-view toggle button

**Location:** in the HTML, immediately after the `#fs-btn` Full Screen
button (currently the line just after `<button id="fs-btn" ...>`).

```html
<button id="prev-btn"
        class="btn btn-sm prev-toggle-btn"
        onclick="togglePreviousState()"
        disabled
        style="margin-left:.4rem;">&#x21D4; Show Previous</button>
```

---

### 3.6 Add the full-screen tray control row

**Location:** inside `#fs-op-tray`, as a new row above `#fs-ops-list`.

Replace:

```html
  <div id="fs-op-tray">
    <ul id="fs-ops-list"></ul>
  </div>
```

With:

```html
  <div id="fs-op-tray">
    <div id="fs-tray-controls"
         style="display:flex; gap:.5rem; margin-bottom:.35rem; padding-bottom:.35rem;
                border-bottom:1px solid rgba(255,255,255,.12);">
      <button class="btn btn-sm prev-toggle-btn"
              onclick="togglePreviousState()"
              disabled>&#x21D4; Show Previous</button>
    </div>
    <ul id="fs-ops-list"></ul>
  </div>
```

---

### 3.7 Sync button state on `enterFullscreen()`

The full-screen tray button appears for the first time when the overlay
opens.  Call `_updatePrevToggle()` at the end of `enterFullscreen()` so
it immediately reflects the current `showingPrev` / `prevVisHtml` state:

```javascript
  window.enterFullscreen = function() {
    // ... existing code ...
    renderFsOps(currentOps, fsLastIsMyTurn);
    _updatePrevToggle();                       // ← add this line
    document.addEventListener('keydown', _onFsKey);
  };
```

---

### 3.8 CSS: "showing-prev" watermark

Add to the `<style>` block in `game.html`:

```css
/* ── M5: previous-state watermark ── */
#vis-display { position: relative; }   /* needed for ::before anchor */

#vis-display.showing-prev::before {
  content: 'PREVIOUS STATE';
  position: absolute;
  top: 0; left: 0; right: 0;
  padding: .18rem 0;
  background: rgba(255, 140, 0, .16);
  border-bottom: 2px solid rgba(255, 140, 0, .55);
  color: rgba(255, 160, 0, .90);
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .14em;
  text-align: center;
  pointer-events: none;
  z-index: 5;
}
```

This pseudo-element follows `#vis-display` wherever it lives (normal card
or full-screen overlay) because it is scoped to the element, not to a
wrapper.  `pointer-events: none` ensures it does not block Tier-2 canvas
clicks.

---

## 4. Behaviour summary

| Situation | Result |
|---|---|
| Step 0 (initial state) | `prevVisHtml = ''`; both buttons disabled |
| After first operator applied | `prevVisHtml` set to step-0 vis; buttons enabled |
| Click "Show Previous" | Swaps innerHTML to `prevVisHtml`; button text → "Show Current"; orange watermark appears |
| Click "Show Current" | Restores innerHTML to `currentVisHtml`; button text → "Show Previous"; watermark hidden |
| New `state_update` arrives (any player) | `showingPrev` reset to `false`; new vis rendered; prev cache rotated; buttons updated |
| Enter full-screen while showing prev | Previous vis is visible in overlay; tray button says "Show Current"; watermark shows |
| Exit full-screen | Toggle state preserved; normal view shows same vis (prev or current) as before |
| Game with text-only state (no vis_html) | `prevVisHtml` cleared; buttons remain disabled |
| `setupHitCanvas()` after toggle | Re-parses `#wsz6-regions` script in the newly displayed HTML; Tier-2 hit-testing works on both prev and current vis |

---

## 5. Files changed

| File | Change |
|---|---|
| `wsz6_portal/templates/wsz6_play/game.html` | All changes — JS vars, `onStateUpdate`, helper functions, HTML buttons, CSS |

No other files change.

---

## 6. Test checklist

- [ ] At step 0 both "Show Previous" buttons (normal + full-screen tray) are disabled.
- [ ] After the first operator is applied, both buttons become enabled.
- [ ] Clicking "Show Previous" in normal view:
  - [ ] Displays the previous state's vis HTML.
  - [ ] Orange "PREVIOUS STATE" watermark banner appears at the top of the vis area.
  - [ ] Button text changes to "Show Current".
- [ ] Clicking "Show Current" restores the current state vis and hides the watermark.
- [ ] A new opponent move while showing previous:
  - [ ] Automatically reverts to "show current".
  - [ ] Button text reverts to "Show Previous".
  - [ ] Watermark disappears.
- [ ] Full-screen mode:
  - [ ] Tray button disabled at step 0; enabled after first move.
  - [ ] Toggle works identically to normal view.
  - [ ] Watermark visible in full-screen overlay when in previous-state mode.
  - [ ] New move in full-screen auto-reverts toggle.
- [ ] Tier-2 canvas (e.g. Click-the-Word or Pixel Probe):
  - [ ] After toggling to previous, hover highlights and click handlers work on the
        previous state's canvas regions (setupHitCanvas re-runs on toggle).
  - [ ] Toggling back to current re-establishes current-state canvas regions.
- [ ] Text-only game (no vis_html): buttons remain disabled throughout the session.
- [ ] Undo: after undo, prev cache still holds the state before the undone move;
      toggle shows that state (two steps back from the undone position).
- [ ] Rapid moves (e.g. quick operator applications): toggle is always consistent
      with the most recently received `state_update`.
