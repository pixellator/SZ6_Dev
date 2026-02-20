# Vis-M4-Plan.md — Full-Screen Mode

**Date:** 2026-02-19
**Milestone:** M4 from VIS_DEV_PLAN.md

---

## Context

M0 (transition history), M1 (SVG vis rendering), and M2 (image assets) are complete.
M4 adds a full-screen overlay for the vis display, replicating the SOLUZION5 experience
of an immersive, chrome-free game view where the operator list auto-hides and slides up
from the bottom when needed.

This is **100% client-side** — only `game.html` changes.  No server, URL, or Python
changes are required.

The existing file-edit overlay (`#file-edit-overlay`, `z-index: 1000`,
`position: fixed`) is the established pattern to follow.

---

## Critical File

**`wsz6_portal/templates/wsz6_play/game.html`**

Three sections touched: `<style>`, the HTML body, and the JS IIFE.

---

## Current layout (relevant excerpt)

```
.game-wrap (2-col grid)
  left col
    .card
      #vis-display   ← SVG vis (display:none when no vis)
      #state-display ← text fallback <pre>
    #turn-banner
    #transition-history (details/ol)
  right col  .card
    #ops-list
    #param-form
    Undo / Help / Pause / Rematch buttons
#file-edit-overlay  (position:fixed, z-index:1000)
```

---

## Approach: DOM-move (not clone)

On `enterFullscreen()`, the existing `#vis-display` element is **moved** (not cloned)
into the overlay.  On `exitFullscreen()`, it is **restored** to its exact original
position using saved `parentNode` + `nextSibling` references.  This means:

- State updates from the server update `#vis-display.innerHTML` normally; the
  location in the DOM (inside the overlay) does not matter to `onStateUpdate`.
- No double-rendering; the vis module is not called again.
- Exiting full-screen is instant — no re-render needed.

---

## 1 — CSS additions (inside `<style>`)

```css
/* ── Full-screen overlay ── */
#fs-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: #111;
  display: flex; align-items: center; justify-content: center;
}

/* vis-display sizing inside the overlay */
#fs-overlay #vis-display {
  width: 100%; height: 100%;
  max-width: none; padding: 1.5rem;
  display: flex; align-items: center; justify-content: center;
  overflow: auto; box-sizing: border-box;
}
/* Scale SVGs to fill the screen */
#fs-overlay #vis-display svg { max-height: 90vh; width: 100%; }

/* ✕ button — always visible top-right */
#fs-close {
  position: absolute; top: .8rem; right: .8rem;
  background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.35);
  color: #fff; font-size: 1.1rem; line-height: 1;
  width: 2.2rem; height: 2.2rem; border-radius: 50%;
  cursor: pointer; z-index: 10000;
  display: flex; align-items: center; justify-content: center;
}
#fs-close:hover { background: rgba(255,255,255,.32); }

/* Operator tray — slides up from bottom on pointer proximity */
#fs-op-tray {
  position: absolute; bottom: 0; left: 0; right: 0;
  background: rgba(10,10,10,.82); backdrop-filter: blur(6px);
  padding: .65rem 1rem;
  transform: translateY(100%);
  transition: transform .28s ease;
  z-index: 10000;
}
#fs-op-tray.visible { transform: translateY(0); }
#fs-ops-list { list-style: none; margin: 0; padding: 0;
               display: flex; flex-wrap: wrap; gap: .4rem; }
#fs-ops-list li button {
  background: rgba(255,255,255,.12); color: #eee;
  border: 1px solid rgba(255,255,255,.25); border-radius: 4px;
  padding: .35rem .75rem; cursor: pointer; font-size: .88rem;
}
#fs-ops-list li button.applicable {
  background: rgba(80,180,100,.35); border-color: rgba(100,220,120,.6); color: #dfffdf;
}
#fs-ops-list li button.applicable:hover { background: rgba(80,180,100,.55); }
#fs-ops-list li button:disabled { opacity: .4; cursor: not-allowed; }

/* Entry button (shown only when vis is active) */
#fs-btn { margin-top: .5rem; display: none; }
```

---

## 2 — HTML additions

### A. Full-screen entry button
Add immediately after the `.card` that wraps `#vis-display` (still inside the left
column `<div>`):

```html
<button id="fs-btn" class="btn btn-sm"
        style="background:#444; color:#fff;"
        onclick="enterFullscreen()">&#x26F6; Full Screen</button>
```

### B. Full-screen overlay
Add just before the existing `#file-edit-overlay` div:

```html
<!-- ── Full-screen vis overlay ─────────────────────────────────────── -->
<div id="fs-overlay" style="display:none;">
  <button id="fs-close" onclick="exitFullscreen()" title="Exit (Esc)">&#x2715;</button>
  <!-- #vis-display is moved here by enterFullscreen(), restored by exitFullscreen() -->
  <div id="fs-op-tray">
    <ul id="fs-ops-list"></ul>
  </div>
</div>
```

---

## 3 — JS additions (inside the IIFE)

### A. New state variables (add alongside existing `let` declarations)

```javascript
let fsActive         = false;
let fsVisParent      = null;   // #vis-display's original parentNode
let fsVisNextSibling = null;   // original nextSibling for exact restore
let fsLastIsMyTurn   = false;  // replayed into renderFsOps on each state_update
```

### B. `enterFullscreen` / `exitFullscreen`

```javascript
window.enterFullscreen = function() {
  if (fsActive) return;
  const visEl = document.getElementById('vis-display');
  if (!visEl || visEl.style.display === 'none') return;

  fsVisParent      = visEl.parentNode;
  fsVisNextSibling = visEl.nextSibling;
  fsActive         = true;

  const overlay = document.getElementById('fs-overlay');
  // Insert vis-display just after #fs-close (before the tray)
  const tray = document.getElementById('fs-op-tray');
  overlay.insertBefore(visEl, tray);
  overlay.style.display = 'flex';

  renderFsOps(currentOps, fsLastIsMyTurn);
  document.addEventListener('keydown', _onFsKey);
};

window.exitFullscreen = function() {
  if (!fsActive) return;
  fsActive = false;

  const visEl   = document.getElementById('vis-display');
  const overlay = document.getElementById('fs-overlay');

  if (fsVisNextSibling) {
    fsVisParent.insertBefore(visEl, fsVisNextSibling);
  } else {
    fsVisParent.appendChild(visEl);
  }

  overlay.style.display = 'none';
  document.getElementById('fs-op-tray').classList.remove('visible');
  document.removeEventListener('keydown', _onFsKey);
};

function _onFsKey(e) {
  if (e.key === 'Escape') exitFullscreen();
}
```

### C. Pointer-proximity tray (self-contained IIFE, runs once at load)

```javascript
(function() {
  const overlay = document.getElementById('fs-overlay');
  overlay.addEventListener('pointermove', function(e) {
    if (!fsActive) return;
    const tray   = document.getElementById('fs-op-tray');
    const thresh = overlay.clientHeight * 0.88;   // bottom 12%
    if (e.clientY >= thresh) tray.classList.add('visible');
    else                     tray.classList.remove('visible');
  });
})();
```

### D. `renderFsOps` (dark-themed, mirrors `renderOps` for the tray)

```javascript
function renderFsOps(ops, isMyTurn) {
  const list = document.getElementById('fs-ops-list');
  if (!list) return;
  if (!ops || ops.length === 0) {
    list.innerHTML =
      '<li style="color:#aaa; font-style:italic; font-size:.85rem;">No operators</li>';
    return;
  }
  let html = '';
  for (const op of ops) {
    const canApply = isMyTurn && op.applicable;
    html += `<li><button class="${canApply ? 'applicable' : ''}"
                 onclick="applyOp(${op.index})"
                 ${canApply ? '' : 'disabled'}>${esc(op.name)}</button></li>`;
  }
  list.innerHTML = html;
}
```

### E. Two additions inside the existing `onStateUpdate(msg)` function

**After the `if (msg.vis_html) { … } else { … }` block:**

```javascript
// Show/hide full-screen button; auto-exit if vis vanishes.
const fsBtn = document.getElementById('fs-btn');
if (msg.vis_html) {
  fsBtn.style.display = 'inline-block';
} else {
  fsBtn.style.display = 'none';
  if (fsActive) exitFullscreen();
}
```

**After the existing `renderOps(msg.operators, isMyTurn)` call:**

```javascript
fsLastIsMyTurn = isMyTurn;
if (fsActive) renderFsOps(currentOps, isMyTurn);
```

---

## Behaviour Summary

| Trigger | Effect |
|---|---|
| "⛶ Full Screen" button (below vis card) | `#vis-display` moved into overlay; overlay shown |
| Esc key | `exitFullscreen()` — vis restored in place |
| ✕ button (top-right of overlay) | Same as Esc |
| Pointer enters bottom 12% of overlay | Operator tray slides up |
| Pointer leaves bottom 12% | Tray slides back down |
| State update arrives (any player's move) | `vis_html` updates in-place; tray ops re-rendered |
| Operator applied from tray | Normal `applyOp()` path; game continues in full-screen |
| Game ends / text-only state | `exitFullscreen()` called automatically |

---

## Test Checklist

- [ ] Full-screen button hidden for text-only games; visible when `vis_html` present.
- [ ] Entering full-screen hides all normal page chrome (nav, op panel, etc.).
- [ ] Vis fills screen; SVG `viewBox` scales correctly on landscape and portrait viewports.
- [ ] Moving pointer to bottom 12% reveals tray; moving away hides it.
- [ ] Esc and ✕ both exit full-screen and restore vis to its exact original DOM location.
- [ ] Operator buttons in tray are dark-themed; applicable ops are green-tinted.
- [ ] Clicking a tray operator applies it; vis updates in full-screen without exiting.
- [ ] Tray op list reflects the correct applicable set after each move.
- [ ] Opponent / bot moves update vis in full-screen automatically.
- [ ] At game-over the tray shows "No operators" and ✕ is still functional.
- [ ] Re-entering full-screen after exiting works cleanly (no DOM drift).
- [ ] `#file-edit-overlay` (z-index 1000) is covered by `#fs-overlay` (z-index 9999).
