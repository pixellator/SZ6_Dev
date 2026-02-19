#!/usr/bin/env python3
'''Textual_SOLUZION6.py

Textual game engine for SOLUZION6 problem formulations.
Combines the functionality of Text_SOLUZION5.py and Select_Roles.py.

Loads a SZ6 problem formulation from a .py file named on the command
line, manages role assignments interactively (subsuming the old
Select_Roles.py), creates an SZ_Solving_Session, and runs the game
or puzzle in the terminal.

Usage:
  python3 Textual_SOLUZION6.py <FormulationModuleName>
Example:
  python3 Textual_SOLUZION6.py Tic_Tac_Toe_SZ6

Supports:
  - Single-player puzzles (no role dialog needed)
  - Multi-role games with player cueing and role-specific state views
  - Parameterized operators (prompts user for each argument)
  - Transition messages (jit_transition on new state)
  - Back / undo, Help, Quit commands

S. Tanimoto, Feb 2026.
'''

import sys
import os
import re
import glob
import datetime
import subprocess
import importlib.util
import soluzion6_02 as sz
import sz_sessions6_02 as szs

TITLE = "Textual SOLUZION6 -- Interactive Game/Puzzle Engine"
DEBUG = False

# -----------------------------------------------------------------------
# MODULE-LEVEL STATE  (used so get_args_for_op can access current state)
# -----------------------------------------------------------------------

CURRENT_STATE = None   # Updated each iteration of the game loop.


# =======================================================================
# SECTION 1:  LOADING THE PROBLEM FORMULATION
# =======================================================================

def load_module(module_name):
    '''Load and return the Python module at <module_name>.py.'''
    try:
        spec   = importlib.util.spec_from_file_location(module_name,
                                                        module_name + ".py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"Error loading formulation '{module_name}': {e}")
        sys.exit(1)


def find_formulation(module):
    '''Return the first SZ_Formulation instance found as a module-level
    attribute.  Exits if none is found.'''
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if isinstance(obj, sz.SZ_Formulation):
            if DEBUG:
                print(f"Found formulation object: '{attr_name}'")
            return obj
    print(f"No SZ_Formulation instance found in module '{module.__name__}'.")
    sys.exit(1)


def _has_file_edit_ops(formulation):
    '''Return True if any operator in the formulation has at least one
    param with type "file_edit".

    Called after initialize_problem() so that formulations which build
    their operator sets lazily (e.g. inside initialize_problem) are
    handled correctly.  Callable params are skipped because they cannot
    be inspected without a live state.
    '''
    if formulation.operators is None:
        return False
    for op in formulation.operators.operators:
        params = op.params
        if callable(params):
            continue
        for p in (params or []):
            if p.get('type') == 'file_edit':
                return True
    return False


def _make_session_folder(game_name):
    '''Create and return the path to a new per-session working directory:

        play-time-dynamic-docs/<game-name>/session-YYYY-MM-DD-HH-MM-sNNN/

    The sNNN suffix (e.g. s001, s002) disambiguates sessions started
    within the same calendar minute.
    '''
    safe_name = re.sub(r'[^\w\-]', '-', game_name)
    game_dir  = os.path.join("play-time-dynamic-docs", safe_name)
    stamp     = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
    existing  = glob.glob(os.path.join(game_dir, f"session-{stamp}-s*"))
    n         = len(existing) + 1
    folder    = os.path.join(game_dir, f"session-{stamp}-s{n:03d}")
    os.makedirs(folder, exist_ok=True)
    return folder


# =======================================================================
# SECTION 2:  ROLE SETUP  (subsumes Select_Roles.py)
# =======================================================================

def _is_observer(role):
    return role.name.lower() == "observer"


def _default_roles_spec():
    '''Minimal single-role spec for formulations that define none.'''
    spec             = sz.SZ_Roles_Spec()
    spec.roles       = [sz.SZ_Role(name='Player',
                                   description='The sole player/solver.')]
    spec.min_players_to_start = 1
    spec.max_players          = 1
    return spec


def setup_roles(formulation):
    '''Interactively build and return (roles_spec, role_assignments, players).

    roles_spec      -- the SZ_Roles_Spec from the formulation (or a default).
    role_assignments -- SZ_Role_Assignments with player_ids assigned to roles.
    players          -- list of player-name strings (the player_id values).
    '''
    if hasattr(formulation, 'roles_spec') and formulation.roles_spec:
        roles_spec = formulation.roles_spec
    else:
        print("(No roles_spec in formulation; using single-player default.)")
        roles_spec = _default_roles_spec()
        formulation.roles_spec = roles_spec

    roles   = roles_spec.roles
    players = []
    role_assignments = szs.SZ_Role_Assignments()

    # Default: assign "Player N" to each non-observer role in order.
    player_counter = 1
    for role_num, role in enumerate(roles):
        if not _is_observer(role):
            name = f"Player {player_counter}"
            players.append(name)
            role_assignments.add_player_in_role(name, role_num)
            player_counter += 1

    # Single non-observer role: skip the dialog entirely.
    if _count_active_non_obs(roles, role_assignments) <= 1 and len(roles) <= 1:
        if players:
            print(f"Single-player game.  Player: {players[0]}\n")
        return roles_spec, role_assignments, players

    # Multi-role (or observer-inclusive): run the interactive dialog.
    min_needed = getattr(roles_spec, 'min_players_to_start', 1)
    done = False
    while not done:
        _print_assignments(roles, role_assignments, players)
        resp = input("Enter a, b, c, or d: ").strip().upper()
        if not resp:
            continue
        ch = resp[0]
        if ch == 'A':
            active = _count_active_non_obs(roles, role_assignments)
            if active < min_needed:
                print(f"Need at least {min_needed} non-observer role(s) filled "
                      f"(currently {active}).  Please assign more players.")
            else:
                done = True
        elif ch == 'B':
            _change_player_name(players, role_assignments)
        elif ch == 'C':
            _add_player(players)
        elif ch == 'D':
            _edit_role_assignment(roles, role_assignments, players)
        else:
            print("Unknown choice; please enter a, b, c, or d.")

    return roles_spec, role_assignments, players


def _count_active_non_obs(roles, role_assignments):
    '''Count non-observer roles that have at least one player assigned.'''
    return sum(
        1 for rn, role in enumerate(roles)
        if not _is_observer(role)
        and role_assignments.get_players_in_role(rn)
    )


def _print_assignments(roles, role_assignments, players):
    print()
    print("+------------------------------------------+")
    print("|  PLAYER(S): SELECT YOUR ROLE(S)          |")
    print("|  Current roles and assignments:          |")
    print("|                                          |")
    print("|  ROLE                   PLAYER(S)        |")
    print("|  ----                   ---------        |")
    for rn, role in enumerate(roles):
        assigned   = role_assignments.get_players_in_role(rn)
        pstr       = ', '.join(assigned) if assigned else '(none)'
        print(f"|  {role.name}: {pstr}")
    print("|                                          |")
    print("|  Choices:                                |")
    print("|    a. Proceed with current assignments   |")
    print("|    b. Change a player name               |")
    print("|    c. Add a new player                   |")
    print("|    d. Edit assignment for a role         |")
    print("+------------------------------------------+")


def _show_players(players):
    print("\nPlayer #    Name\n--------    ----")
    for i, name in enumerate(players):
        print(f"  {i + 1}         {name}")


def _show_roles(roles):
    print("\nRole #    Name\n------    ----")
    for i, role in enumerate(roles):
        print(f"  {i + 1}       {role.name}  --  {role.description}")


def _change_player_name(players, role_assignments):
    _show_players(players)
    while True:
        resp = input("Number of player to rename (or c to cancel): ").strip()
        if resp.lower() == 'c':
            return
        try:
            idx = int(resp) - 1
            if not (0 <= idx < len(players)):
                print(f"Must be between 1 and {len(players)}.")
                continue
            old_name = players[idx]
            new_name = input("New name: ").strip()
            if not new_name:
                print("Name cannot be empty.")
                continue
            # Update role_assignments: replace old_name with new_name everywhere.
            for rn in list(role_assignments.player_to_role[old_name]):
                plist = role_assignments.role_to_player[rn]
                for k, pid in enumerate(plist):
                    if pid == old_name:
                        plist[k] = new_name
            role_assignments.player_to_role[new_name] = \
                role_assignments.player_to_role.pop(old_name)
            players[idx] = new_name
            return
        except ValueError:
            print("Invalid number.")


def _add_player(players):
    name = input("Name for new player: ").strip()
    if name:
        players.append(name)
        print(f"Added player: {name}")
    else:
        print("Name cannot be empty; player not added.")


def _edit_role_assignment(roles, role_assignments, players):
    _show_roles(roles)
    role_num = None
    while role_num is None:
        resp = input("Role number to reassign (or c to cancel): ").strip()
        if resp.lower() == 'c':
            return
        try:
            rn = int(resp) - 1
            if 0 <= rn < len(roles):
                role_num = rn
            else:
                print(f"Must be between 1 and {len(roles)}.")
        except ValueError:
            print("Invalid number.")

    while True:
        _show_players(players)
        print("Enter a positive player number to assign, negative to remove.")
        resp = input("Player number (or c to cancel): ").strip()
        if resp.lower() == 'c':
            return
        try:
            pnum   = int(resp)
            remove = (pnum < 0)
            pnum   = abs(pnum) - 1
            if not (0 <= pnum < len(players)):
                print(f"Must be between 1 and {len(players)} (or its negative).")
                continue
            pid = players[pnum]
            if remove:
                plist = role_assignments.role_to_player[role_num]
                if pid in plist:
                    plist.remove(pid)
                    role_assignments.player_to_role[pid].remove(role_num)
                else:
                    print(f"{pid} was not assigned to {roles[role_num].name}.")
            else:
                if pid not in role_assignments.role_to_player[role_num]:
                    role_assignments.add_player_in_role(pid, role_num)
                else:
                    print(f"{pid} is already assigned to {roles[role_num].name}.")
            return
        except ValueError:
            print("Invalid number.")


# =======================================================================
# SECTION 3:  PLAYER CUEING
# =======================================================================

_cue_last_player   = None
_cue_last_role_num = None


def cue_player(state, roles, role_assignments):
    '''Print a handover prompt when it is time for a player to take the
    keyboard.  Suppresses the prompt when the same player continues in
    the same role.  Updates the module-level cue-tracking variables and
    returns the role_num of the player who confirmed.
    '''
    global _cue_last_player, _cue_last_role_num

    role_num   = state.current_role_num
    assigned   = role_assignments.get_players_in_role(role_num)
    player     = assigned[0] if assigned else (_cue_last_player or "Player 1")
    role_name  = roles[role_num].name if role_num < len(roles) else str(role_num)

    same_player = (player   == _cue_last_player)
    same_role   = (role_num == _cue_last_role_num)
    bar         = "-" * 52

    print(bar)
    if same_player and same_role:
        print(f"  ({player} continuing in role: {role_name})")
    elif same_player:
        print(f"  ({player} switching to role: {role_name})")
    else:
        prev = _cue_last_player or "(nobody)"
        print(f"  {prev}: please hand the keyboard to {player}.")
        print(f"  {player}, you are playing the role of: {role_name}.")
    print(bar)
    input("  Press Enter to confirm. ")

    _cue_last_player   = player
    _cue_last_role_num = role_num
    return role_num


# =======================================================================
# SECTION 4:  OPERATOR APPLICABILITY AND PARAMETERIZED OPERATORS
# =======================================================================

def get_applicability_vector(state, operators, role_num=None):
    '''Return a list of booleans, one per operator.

    If role_num is given and does not match state.current_role_num,
    all entries are False (safety check: wrong player at the keyboard).

    When role_num is given, operators that carry an explicit op.role
    attribute are additionally filtered: an op with op.role != role_num
    is never shown to the current player, even if its precondition is
    met.  This is essential for parallel-input states where multiple
    players have applicable operators simultaneously.

    Operators with op.role == None are never filtered by role.
    '''
    if role_num is not None and state.current_role_num != role_num:
        return [False] * len(operators)
    result = []
    for op in operators:
        if role_num is not None and op.role is not None and op.role != role_num:
            result.append(False)
        else:
            result.append(op.precond_func(state))
    return result


def get_op_name(op, state):
    '''Return the operator's display name.
    Supports both a plain string and a callable (function of state).
    '''
    if callable(op.name):
        return op.name(state)
    return op.name


def get_args_for_op(op):
    '''Prompt the user for each parameter of a parameterized operator.
    Returns a list of argument values in the order specified by op.params.
    If op.params is itself callable (depends on current state), evaluate
    it first.
    '''
    if not op.params:
        return []
    p_list = op.params
    if callable(p_list):
        p_list = p_list(CURRENT_STATE)
    return [_prompt_one_arg(param, op) for param in p_list]


NEG_INF = float('-inf')
POS_INF = float('inf')


def _prompt_one_arg(param, op):
    p_type = param.get('type', 'str')
    if p_type == 'int':       return _prompt_int(param, op)
    if p_type == 'float':     return _prompt_float(param, op)
    if p_type == 'file_edit': return _handle_file_edit(param, op)
    return _prompt_str(param, op)


def _handle_file_edit(param, op):
    '''Open param["file_path"] in the system editor and return its contents.

    If the file does not yet exist it is seeded with param["initial_text"].
    The editor command is taken from the EDITOR environment variable;
    "nano" is used as the default.
    '''
    file_path    = param['file_path']
    initial_text = param.get('initial_text', '')
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(initial_text)
    editor = os.getenv('EDITOR', 'nano')
    print(f"  Opening '{editor}' to edit: {file_path}")
    print("  Save and exit the editor when done.")
    subprocess.run([editor, file_path])
    with open(file_path, 'r') as f:
        return f.read()


def _prompt_int(param, op):
    lo     = param.get('min', NEG_INF)
    hi     = param.get('max', POS_INF)
    prompt = (f"  Enter an integer in [{lo}..{hi}]"
              f" for parameter '{param['name']}'"
              f" (operator: \"{op.name}\"): ")
    while True:
        try:
            v = int(input(prompt))
            if   v < lo: print("  Too low.  Try again.")
            elif v > hi: print("  Too high. Try again.")
            else:        return v
        except ValueError:
            print("  Not a valid integer.  Try again.")


def _prompt_float(param, op):
    lo     = param.get('min', NEG_INF)
    hi     = param.get('max', POS_INF)
    prompt = (f"  Enter a number in [{lo}..{hi}]"
              f" for parameter '{param['name']}'"
              f" (operator: \"{op.name}\"): ")
    while True:
        try:
            v = float(input(prompt))
            if   v < lo: print("  Too low.  Try again.")
            elif v > hi: print("  Too high. Try again.")
            else:        return v
        except ValueError:
            print("  Not a valid number.  Try again.")


def _prompt_str(param, op):
    prompt = (f"  Enter a value for parameter '{param['name']}'"
              f" (operator: \"{op.name}\"): ")
    return input(prompt)


# =======================================================================
# SECTION 5:  TRANSITIONS
# =======================================================================

def handle_transition(new_state):
    '''Display the jit_transition message attached to new_state, if any.'''
    msg = getattr(new_state, 'jit_transition', None)
    if msg:
        _display_framed(msg)


def _display_framed(text):
    '''Print text inside a simple box frame.'''
    text  = text.rstrip('\n')
    lines = text.split('\n')
    width = max(len(line) for line in lines)
    bar   = "+-" + "-" * width + "-+"
    print(bar)
    for line in lines:
        print("| " + line + " " * (width - len(line)) + " |")
    print(bar)


# =======================================================================
# SECTION 6:  INSTRUCTIONS
# =======================================================================

def show_instructions():
    print('''
INSTRUCTIONS:
  <number>  Apply the operator with that number.
  B         Go back one step (undo last move).
  H         Show these instructions.
  Q         Quit the session.

The current state of the game or puzzle is shown at each step.
Operators that are applicable in the current state are listed by number.
''')


# =======================================================================
# SECTION 7:  MAIN GAME LOOP
# =======================================================================

def mainloop(session, roles_spec, role_assignments):
    '''Run the interactive game/puzzle loop.

    session          -- SZ_Solving_Session instance.
    roles_spec       -- SZ_Roles_Spec from the formulation.
    role_assignments -- SZ_Role_Assignments populated during setup.
    '''
    global CURRENT_STATE

    formulation = session.formulation
    operators   = formulation.operators.operators
    roles       = roles_spec.roles

    # Determine whether multi-role cueing is needed.
    multi_role = (_count_active_non_obs(roles, role_assignments) > 1)

    state_stack = [session.current_state]
    step        = 0
    depth       = 0

    while True:
        CURRENT_STATE        = state_stack[-1]
        session.current_state = CURRENT_STATE

        print(f"\nStep {step}, Depth {depth}")

        # ---- Parallel-phase notice ----
        # Shown once per player handoff so everyone knows not to peek.
        if getattr(CURRENT_STATE, 'parallel', False):
            print("*** PARALLEL INPUT PHASE: each player chooses independently. ***")
            print("*** Please look away from the screen until it is your turn.  ***")

        # ---- Cue the right player (multi-role games only) ----
        if multi_role:
            confirmed_role_num = cue_player(CURRENT_STATE, roles,
                                            role_assignments)
        else:
            confirmed_role_num = None   # Show all applicable ops.

        # ---- Display the current state ----
        if hasattr(CURRENT_STATE, 'text_view_for_role') and multi_role:
            print(CURRENT_STATE.text_view_for_role(
                CURRENT_STATE.current_role_num))
        else:
            print(CURRENT_STATE)

        # ---- Compute which operators are applicable ----
        app_vec = get_applicability_vector(CURRENT_STATE, operators,
                                           confirmed_role_num)

        # ---- Check for goal ----
        try:
            at_goal = CURRENT_STATE.is_goal()
        except Exception:
            at_goal = False

        if at_goal:
            try:
                msg = CURRENT_STATE.goal_message()
            except Exception:
                msg = "Goal state reached!"
            print(f"\nCONGRATULATIONS!  {msg}")
            answer = input("\nContinue exploring? (Y/N) >> ").strip().upper()
            if answer != 'Y':
                return

        # ---- List applicable operators ----
        any_shown = False
        for i, op in enumerate(operators):
            if app_vec[i]:
                print(f"  {i}: {get_op_name(op, CURRENT_STATE)}")
                any_shown = True
        if not any_shown:
            print("  (No operators are currently applicable.)")

        # ---- Get command ----
        command = input(
            "Command  [number / B=back / H=help / Q=quit] >> "
        ).strip()

        if not command:
            continue
        cmd_upper = command.upper()

        if cmd_upper == 'Q':
            break
        if cmd_upper == 'H':
            show_instructions()
            continue
        if cmd_upper == 'B':
            if len(state_stack) > 1:
                state_stack.pop()
                depth -= 1
                step  += 1
            else:
                print("Already at the initial state; cannot go further back.")
            continue

        # ---- Parse operator number ----
        try:
            i = int(command)
        except ValueError:
            print("Unknown command.  Enter a number, B, H, or Q.")
            continue

        if not (0 <= i < len(operators)):
            print(f"No operator with number {i}.")
            continue

        if not app_vec[i]:
            print(f"Operator {i} is not applicable in the current state.")
            continue

        # ---- Apply the operator ----
        op = operators[i]
        if op.params:
            args      = get_args_for_op(op)
            new_state = op.state_xition_func(CURRENT_STATE, args)
        else:
            new_state = op.state_xition_func(CURRENT_STATE)

        handle_transition(new_state)
        state_stack.append(new_state)
        depth += 1
        step  += 1


# =======================================================================
# SECTION 8:  ENTRY POINT
# =======================================================================

def main():
    print(TITLE)
    print()

    if len(sys.argv) < 2:
        print("Usage:   python3 Textual_SOLUZION6.py <FormulationModuleName>")
        print("Example: python3 Textual_SOLUZION6.py Tic_Tac_Toe_SZ6")
        sys.exit(1)

    module_name = sys.argv[1]
    print(f"Loading formulation module: {module_name}")
    module      = load_module(module_name)
    formulation = find_formulation(module)

    name    = getattr(formulation.metadata, 'name',            module_name)
    version = getattr(formulation.metadata, 'problem_version', '?')
    desc    = getattr(formulation.metadata, 'brief_desc',      '')
    print(f"\nFormulation: {name}  (version {version})")
    if desc:
        print(f"Description: {desc}")

    # ---- Role assignment ----
    roles_spec, role_assignments, players = setup_roles(formulation)
    print("\nRole assignments confirmed.")

    # ---- Initialize the problem instance ----
    # First pass: call with no config so operators are built (some formulations
    # create operators lazily inside initialize_problem).
    print(f"\nInitializing {name} ...")
    initial_state = formulation.initialize_problem(config={})

    # Second pass: if any operator has a file_edit param, create the
    # per-session folder and re-initialize so the formulation can embed
    # the real path into its operator closures.
    # Games without file-editing operators skip this entirely, keeping the
    # file system clean of unnecessary timestamped folders.
    if _has_file_edit_ops(formulation):
        session_folder = _make_session_folder(name)
        print(f"Session folder: {session_folder}")
        initial_state = formulation.initialize_problem(
            config={'session_folder': session_folder})

    # ---- Create the session ----
    session = szs.SZ_Solving_Session(
        formulation       = formulation,
        game_instance_data= formulation.instance_data,
        current_state     = initial_state
    )

    # ---- Run ----
    show_instructions()
    mainloop(session, roles_spec, role_assignments)

    print("\nSession finished.  Goodbye!")


if __name__ == '__main__':
    main()
