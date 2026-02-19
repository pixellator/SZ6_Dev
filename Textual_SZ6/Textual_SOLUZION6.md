# Textual_SOLUZION6.py — Documentation

**Version:** 1.0
**Date:** February 2026
**Author:** S. Tanimoto

---

## Overview

`Textual_SOLUZION6.py` is a command-line game engine for SOLUZION6 problem formulations. It provides an interactive terminal interface for single-player puzzles and multi-player games, supporting sophisticated features like parallel input, file editing operators, and remote LLM integration.

The engine combines the functionality of the earlier `Text_SOLUZION5.py` and `Select_Roles.py` into a unified system that uses the new SZ6 class-based formulation architecture.

---

## Quick Start

### Basic Usage

```bash
python3 Textual_SOLUZION6.py <FormulationModuleName>
```

**Example:**
```bash
python3 Textual_SOLUZION6.py Tic_Tac_Toe_SZ6
```

### In-Game Commands

- `<number>` — Apply the operator with that number
- `B` — Go back one step (undo last move)
- `H` — Show help/instructions
- `Q` — Quit the session

---

## Core Features

### 1. Dynamic Formulation Loading

The engine loads problem formulations at runtime by inspecting the specified Python module for an instance of `SZ_Formulation`. No fixed naming convention is required — the engine finds the formulation automatically.

```python
# The engine looks for this pattern:
class MyFormulation(sz.SZ_Formulation):
    ...

MY_GAME = MyFormulation()  # Engine finds this automatically
```

### 2. Role Management

**Single-player games/puzzles:**
Role assignment dialog is skipped automatically. The player is assigned to the sole role.

**Multi-player games:**
Interactive role assignment menu allows players to:
- Accept default assignments (`Player 1` → Role 1, etc.)
- Rename players
- Add additional players
- Reassign roles dynamically

The engine enforces `min_players_to_start` before allowing the game to begin.

### 3. Player Cueing

In multi-role games, the engine prompts for keyboard handoffs between players:

```
----------------------------------------------------
  Player 1: please hand the keyboard to Player 2.
  Player 2, you are playing the role of: O.
----------------------------------------------------
  Press Enter to confirm.
```

Cueing is suppressed when the same player continues in the same role.

### 4. Role-Specific State Views

States may define `text_view_for_role(role_num)` to show different information to different players. This is essential for:
- Hiding opponent choices in parallel-input games
- Masking private information in strategy games
- Customizing instructions per role

### 5. Parameterized Operators

Operators can require arguments via the `params` attribute. The engine prompts the player for each parameter in sequence.

**Supported parameter types:**

| Type | Input Method | Example |
|------|-------------|---------|
| `'int'` | Numeric input with min/max validation | `{'name':'age', 'type':'int', 'min':14, 'max':21}` |
| `'float'` | Numeric input with range validation | `{'name':'weight', 'type':'float', 'min':0.0, 'max':100.0}` |
| `'str'` | Free-text single-line input | `{'name':'prompt', 'type':'str'}` |
| `'file_edit'` | Opens system editor; returns file contents | `{'name':'draft', 'type':'file_edit', 'file_path':'...', 'initial_text':'...'}` |

The `state_xition_func` receives `(state, args)` where `args` is a list of parameter values in the order specified.

### 6. Transition Messages

After an operator is applied, the engine displays the `jit_transition` attribute (if present on the new state) in a framed box:

```
+--------------------------------------------------+
| P1 chose Rock.  P2 chose Scissors.               |
| P1 wins this round!   (P1: +1,  P2: -1)          |
| Scores after round 1: P1 = 1,  P2 = -1           |
+--------------------------------------------------+
```

This is ideal for showing round results, LLM responses, or analysis output.

### 7. Parallel Input (Simultaneous Moves)

Games where multiple players make choices simultaneously (e.g., Rock-Paper-Scissors) set `state.parallel = True`. The engine:

1. Prints a notice: `*** PARALLEL INPUT PHASE: each player chooses independently. ***`
2. Uses `op.role` filtering to show each player only their own operators
3. Serializes input in the terminal (player 1 → player 2), while preserving the formulation's semantics for a future web engine

States use `text_view_for_role` to mask choices as "Made"/"Pending" until both players have submitted, preventing scroll-back cheating.

### 8. File Editing Operators

Operators with `'type': 'file_edit'` params trigger the system text editor:

**Param structure:**
```python
{
    'name':         'draft',
    'type':         'file_edit',
    'file_path':    '/path/to/session-folder/draft.txt',
    'initial_text': 'Placeholder text...',
}
```

**Engine behavior:**
1. Creates `file_path` (seeded with `initial_text`) if it doesn't exist
2. Opens the file in the editor (`$EDITOR` or `nano`)
3. Waits for the editor to exit
4. Reads the file and passes its content as `args[0]` to `state_xition_func`

**Session folder management:**
- The engine detects formulations with `file_edit` params via `_has_file_edit_ops()`
- Creates timestamped session folders only when needed:
  ```
  play-time-dynamic-docs/<game-name>/session-YYYY-MM-DD-HH-MM-sNNN/
  ```
- Games without file editing leave no file-system artifacts

### 9. Remote LLM Integration

Formulations can call external APIs (LLMs, web services, etc.) from within operator transition functions. No engine modifications are needed — the formulation handles all API interaction.

**Pattern:**
```python
def _make_llm_func(api_key, model_name):
    client = genai.Client(api_key=api_key)
    def call_llm(prompt):
        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text
    return call_llm

class MyOperatorSet(sz.SZ_Operator_Set):
    def __init__(self, llm_func):
        ask_op = sz.SZ_Operator(
            name="Ask the LLM",
            state_xition_func=lambda s, args, fn=llm_func: s.apply_prompt(args[0], fn),
            params=[{'name':'prompt', 'type':'str'}]
        )
        self.operators = [ask_op]
```

The LLM response is typically stored in `jit_transition` for framed display.

### 10. Undo / Back

The engine maintains a state stack. Pressing `B` pops the most recent state, allowing players to explore alternate paths. Undo works all the way back to the initial state.

### 11. Goal Detection

After each move, the engine calls `state.is_goal()`. If `True`, it displays `state.goal_message()` and offers the option to continue exploring or quit.

---

## Formulation Requirements

A valid SZ6 formulation file must:

1. **Import the base classes:**
   ```python
   import soluzion6_02 as sz
   ```

2. **Define subclasses:**
   - `SZ_Metadata` — name, version, authors, description
   - `SZ_State` — state representation, `__eq__`, `__hash__`, `__str__`, `is_goal()`, `goal_message()`
   - `SZ_Operator_Set` — list of `SZ_Operator` instances
   - `SZ_Roles_Spec` — list of roles, min/max player counts
   - `SZ_Formulation` — assembles the above + `initialize_problem(config={})`

3. **Export a module-level formulation instance:**
   ```python
   MY_GAME = MyFormulation()
   ```

4. **Implement `initialize_problem(config={})`:**
   ```python
   def initialize_problem(self, config={}):
       initial_state = MyState()
       self.instance_data = sz.SZ_Problem_Instance_Data(
           d={'initial_state': initial_state})
       return initial_state
   ```

**Optional features:**
- `state.text_view_for_role(role_num)` for role-specific views
- `state.jit_transition` for transition messages
- `state.parallel = True` for simultaneous-input phases
- `op.role = <int>` for role-restricted operators
- `op.params` for parameterized operators

---

## Sample Formulations

### 1. Tic_Tac_Toe_SZ6.py

**Type:** Two-player game
**Features:** Multi-role cueing, role-specific operators, win detection
**Operators:** 18 (9 per player: place X/O in each cell)
**Roles:** X, O

Classic two-player Tic-Tac-Toe. Demonstrates alternating turns and goal detection.

---

### 2. Guess_My_Age_SZ6.py

**Type:** Single-player game
**Features:** Parameterized operator (`int` param), random instance data
**Operators:** 1 (`Guess my age` with min/max constraints)
**Roles:** Age Guesser

The computer picks a secret age (14-21); the player guesses until correct. Each guess receives a "too high"/"too low" hint.

**Key design:** Operators are built in `initialize_problem()` so `secret_age` is captured in a closure, allowing multiple independent game sessions.

---

### 3. Missionaries_SZ6.py

**Type:** Single-player puzzle
**Features:** Classic state-space search problem
**Operators:** 5 (one per legal boat-load combination)
**Roles:** Solver

Transfer 3 missionaries and 3 cannibals across a river without missionaries ever being outnumbered on either bank. Demonstrates traditional puzzle formulation in SZ6 structure.

---

### 4. Rock_Paper_Scissors_SZ6.py

**Type:** Two-player game
**Features:** Parallel input, role-restricted operators, multi-round scoring
**Operators:** 7 (3 per player for R/P/S choices + 1 "Start next round")
**Roles:** P1, P2
**Rounds:** 3

Simultaneous-choice game. Each round both players select Rock, Paper, or Scissors. The state sets `parallel = True` during the choosing phase and uses `text_view_for_role` to mask choices as "Made"/"Pending" until both are in. Winner is determined by cumulative score after 3 rounds.

**Key design:** `op.role = P1` or `P2` ensures each player only sees their own three choice operators during the choosing phase, even though both sets are simultaneously applicable.

---

### 5. Trivial_Writing_Game_SZ6.py

**Type:** Single-player writing exercise
**Features:** File editing operator, session folder creation, text analysis
**Operators:** 1 (`Edit your writing` with `file_edit` param)
**Roles:** Writer

Player edits a text file in the system editor. When done, the engine analyzes the file and reports word-frequency counts via `jit_transition`.

**Key design:** The engine detects the `'file_edit'` param type via `_has_file_edit_ops()`, creates a timestamped session folder, and passes it to `initialize_problem(config={'session_folder': ...})` so the formulation can build the full file path.

**File system structure:**
```
play-time-dynamic-docs/
  Trivial-Writing-Game/
    session-2026-02-18-14-37-s001/
      draft.txt
```

---

### 6. Remote_LLM_Test_Game_SZ6.py

**Type:** Single-player interactive session
**Features:** Remote API calls (Gemini LLM), free-text `str` param
**Operators:** 2 (`Send a prompt to the LLM`, `Finish session`)
**Roles:** Prompter
**Dependencies:** `pip install google-genai`
**Environment:** `export GEMINI_API_KEY="your-key-here"`

Player types free-text prompts sent to Gemini 2.5 Flash-Lite. LLM responses are shown as framed transition messages. Player may send multiple prompts before finishing.

**Key design:** The LLM client is built in `initialize_problem()` as a closure-captured callable. The operator's `state_xition_func` calls it and stores the response in `jit_transition`. No engine modifications are needed for remote API integration.

---

## Architecture

### File Structure

```
soluzion6_02.py          — Base classes (SZ_Formulation, SZ_State, SZ_Operator, etc.)
sz_sessions6_02.py       — Session management (SZ_Role_Assignments, SZ_Solving_Session)
Textual_SOLUZION6.py     — Game engine (this file)
<Formulation>_SZ6.py     — Individual problem formulations
```

### Engine Sections

1. **Loading** — Module import, formulation discovery
2. **Role Setup** — Interactive role assignment (subsumes old `Select_Roles.py`)
3. **Player Cueing** — Keyboard handoff prompts for multi-role games
4. **Operator Handling** — Applicability filtering, parameterized operator argument collection
5. **Transitions** — Framed display of `jit_transition` messages
6. **Instructions** — Help text
7. **Main Loop** — State display, command input, operator application, undo stack
8. **Entry Point** — CLI argument parsing, initialization orchestration

### Two-Pass Initialization

For formulations with `file_edit` operators:

1. **First pass:** `initialize_problem(config={})` — builds operators (some formulations create them lazily)
2. **Detection:** `_has_file_edit_ops(formulation)` — inspects `op.params` for `'type': 'file_edit'`
3. **Second pass (if needed):** Create session folder → `initialize_problem(config={'session_folder': ...})`

Games without file editing skip the second pass, leaving no file-system artifacts.

---

## Advanced Topics

### Operator Role Filtering

When `op.role` is set (integer or `None`), `get_applicability_vector()` filters operators by role:

```python
if role_num is not None and op.role is not None and op.role != role_num:
    result.append(False)  # Hide this op from the current player
```

This is essential for parallel-input states where both players' operators have true preconditions simultaneously.

### Callable Params

If `op.params` is a function (not a list), the engine evaluates it at runtime:

```python
if callable(p_list):
    p_list = p_list(CURRENT_STATE)
```

This allows param lists to depend on the current state (e.g., dynamic min/max values).

### State Equality and Hashing

The engine uses `state.__eq__` and `state.__hash__` for state stack management. Proper implementations are required for undo to work correctly.

### Platform Compatibility

- **Linux/macOS:** Fully supported, default editor is `nano`
- **Windows:** Run from WSL for `nano` editor. Native Windows PowerShell/CMD requires setting `$env:EDITOR` to `notepad` or another Windows editor.

---

## Troubleshooting

### "No SZ_Formulation instance found"

The module does not export a formulation instance. Add:
```python
MY_GAME = MyFormulation()
```

### "Need at least N non-observer role(s) filled"

The game requires more players. Add players via the role assignment menu (option `c`), then assign them to roles (option `d`).

### File editing fails (FileNotFoundError on `nano`)

On Windows, run from WSL or set `EDITOR` environment variable to a Windows editor:
```powershell
$env:EDITOR = "notepad"
```

### LLM quota errors (429 RESOURCE_EXHAUSTED)

Free-tier API limits reached. Wait for quota reset (check https://ai.dev/rate-limit) or upgrade to a paid plan.

---

## Future Directions

- **Web engine:** A browser-based engine will handle parallel input natively (simultaneous WebSocket submissions from multiple clients)
- **Observer roles:** Spectator support for streaming games
- **Replay/logging:** Session transcripts for post-game analysis
- **Multiline text params:** `'type': 'multiline_str'` for paragraph-length input
- **Additional param types:** `'file_upload'`, `'image_upload'`, `'audio_record'`

---

## License and Credits

SOLUZION6 framework by S. Tanimoto, 2025-2026.

Sample formulations derived from classic puzzles and games in the public domain.

---

**End of Documentation**
