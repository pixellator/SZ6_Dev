'''Trivial_Writing_Game_SZ6.py

A minimal single-player writing game for SOLUZION6.

The player is prompted to edit a text file using the system editor.
When done, the engine analyzes the file and reports word-frequency
counts.  The session document lives in a structured folder hierarchy:

    play-time-dynamic-docs/<game-name>/session-YYYY-MM-DD-HH-MM-sNNN/

where sNNN (e.g. s001) distinguishes sessions started within the same
minute.

This formulation introduces the 'file_edit' operator param type.
A param dict with 'type': 'file_edit' signals to the engine that
this argument is not typed at the keyboard but obtained by:
  1. Writing 'initial_text' to the file at 'file_path' (if the file
     does not already exist).
  2. Opening 'file_path' in the user's preferred editor (from the
     EDITOR environment variable; falling back to 'nano').
  3. Waiting for the editor to exit, then reading 'file_path' and
     returning its contents as the argument string.

The state_xition_func receives (state, args) where args[0] is the
full text content of the edited file.

This feature is orthogonal to the parallel-input mechanism used in
Rock-Paper-Scissors: a multi-player writing game could give each
player their own 'file_edit' operator (via op.role) pointing to
their own file in the shared session folder.

Status: Initial SZ6 draft, Feb 2026.
'''

SOLUZION_VERSION = 6

import os
import re
import collections

import soluzion6_02 as sz

# ---------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------------------------------

GAME_FOLDER_NAME = "Trivial-Writing-Game"
DRAFT_FILENAME   = "draft.txt"

INITIAL_TEXT = """\
[Replace this placeholder text with your own writing, then save and exit.]

"""

# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class TWG_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = "Trivial Writing Game"
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = "1.0"
        self.authors          = ['S. Tanimoto']
        self.creation_date    = "2026-Feb"
        self.brief_desc = (
            "A minimal single-player writing exercise. "
            "The player edits a text file; when done, the engine reports "
            "word-frequency counts of the document."
        )

# ---------------------------------------------------------------------------
# TEXT ANALYSIS HELPERS
# ---------------------------------------------------------------------------

def _analyze_text(text):
    '''Return a list of (word, count) pairs sorted most-to-least frequent.'''
    words = re.findall(r'\b\w+\b', text.lower())
    return collections.Counter(words).most_common()


def _format_analysis(word_counts):
    '''Format word-frequency results as a multi-line string for display.'''
    if not word_counts:
        return "No words found in the document."
    total = sum(c for _, c in word_counts)
    lines = [
        f"Total words: {total}",
        "",
        f"{'Word':<20}  {'Count':>5}",
        f"{'-'*20}  {'-'*5}",
    ]
    for word, count in word_counts:
        lines.append(f"{word:<20}  {count:>5}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class TWG_State(sz.SZ_State):
    '''
    Phases:
      'writing' -- the player has not yet submitted their document.
      'done'    -- the player submitted; analysis is available.
    '''

    def __init__(self, old=None):
        if old is None:
            self.phase            = 'writing'
            self.total_words      = 0
            self.analysis_text    = ""
            self.current_role_num = 0
        else:
            self.phase            = old.phase
            self.total_words      = old.total_words
            self.analysis_text    = old.analysis_text
            self.current_role_num = old.current_role_num

    def __str__(self):
        return self.text_view_for_role(self.current_role_num)

    def text_view_for_role(self, role_num):
        if self.phase == 'writing':
            return "Phase: Writing.  Edit your document when ready."
        else:
            return (f"Phase: Done.  "
                    f"Total words written: {self.total_words}.")

    def __eq__(self, s):
        return (self.phase       == s.phase and
                self.total_words == s.total_words)

    def __hash__(self):
        return hash(str(self))

    def apply_writing(self, content):
        '''Return a new state after the player submits their document.

        content -- the string read back from the edited file by the engine.
        The word-frequency analysis is computed here and stored in
        jit_transition so the engine displays it in a framed box.
        '''
        news              = TWG_State(old=self)
        word_counts       = _analyze_text(content)
        news.total_words  = sum(c for _, c in word_counts)
        news.analysis_text = _format_analysis(word_counts)
        news.jit_transition = news.analysis_text
        news.phase        = 'done'
        return news

    def is_goal(self):
        return self.phase == 'done'

    def goal_message(self):
        return (f"Document analysis complete!  "
                f"Total words written: {self.total_words}.")

# ---------------------------------------------------------------------------
# OPERATOR SET
# (Built inside initialize_problem() so draft_path can be captured.)
# ---------------------------------------------------------------------------

def _make_operator_set(draft_path):
    '''Return a TWG_Operator_Set whose operator closes over draft_path.

    The 'file_edit' param type is a new convention understood by
    Textual_SOLUZION6.py (and, eventually, the web engine):
      'file_path'    -- absolute path of the file to edit.
      'initial_text' -- text written to the file the first time it is
                        opened (if the file does not yet exist).
    The engine opens the file in the user's editor, waits for the editor
    to exit, reads the file, and passes its content as args[0] to
    state_xition_func.
    '''

    class TWG_Operator_Set(sz.SZ_Operator_Set):
        def __init__(self):
            write_op = sz.SZ_Operator(
                name="Edit your writing",
                precond_func=lambda s: s.phase == 'writing',
                state_xition_func=lambda s, args: s.apply_writing(args[0]),
                params=[{
                    'name':         'draft',
                    'type':         'file_edit',
                    'file_path':    draft_path,
                    'initial_text': INITIAL_TEXT,
                }]
            )
            self.operators = [write_op]

    return TWG_Operator_Set()

# ---------------------------------------------------------------------------
# ROLES
# ---------------------------------------------------------------------------

class TWG_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(
                name='Writer',
                description='Edits a document and receives word-count feedback.'),
        ]
        self.min_players_to_start = 1
        self.max_players          = 1

# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class TWG_Formulation(sz.SZ_Formulation):
    '''Top-level formulation for the Trivial Writing Game.

    initialize_problem() accepts an optional config dict.  When called by
    Textual_SOLUZION6.py (or a web engine), config['session_folder'] is
    the pre-created per-session directory.  When called standalone (self-
    test), a fallback folder is created locally.
    '''

    def __init__(self):
        self.metadata    = TWG_Metadata()
        self.roles_spec  = TWG_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        self.operators   = None   # set in initialize_problem()

    def initialize_problem(self, config={}):
        '''Set up the draft file path, build operators, create initial state.

        config keys (all optional):
          'session_folder' -- path to the per-session working directory
                              created by the engine.  If absent, a fallback
                              "session-test" folder is created locally so
                              standalone testing works without an engine.
        '''
        session_folder = config.get('session_folder', None)
        if session_folder is None:
            session_folder = os.path.join(
                "play-time-dynamic-docs", GAME_FOLDER_NAME, "session-test")
        os.makedirs(session_folder, exist_ok=True)

        draft_path     = os.path.join(session_folder, DRAFT_FILENAME)
        self.operators = _make_operator_set(draft_path)

        initial_state = TWG_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(d={
            'initial_state':  initial_state,
            'session_folder': session_folder,
            'draft_path':     draft_path,
        })
        return initial_state

# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT
# ---------------------------------------------------------------------------

TWG = TWG_Formulation()

# ---------------------------------------------------------------------------
# SELF-TEST  (run with: python3 Trivial_Writing_Game_SZ6.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Trivial Writing Game SZ6 self-test ===\n")

    s = TWG.initialize_problem()   # uses fallback session-test folder
    print(f"Initial state:  {s}")
    print(f"Session folder: {TWG.instance_data.data['session_folder']}")
    print(f"Draft path:     {TWG.instance_data.data['draft_path']}")

    op = TWG.operators.operators[0]
    print(f"\nOperator: '{op.name}'")
    print(f"Params:   {op.params}")

    # Simulate what the engine would do: supply file content directly
    # rather than opening an interactive editor.
    test_text = (
        "The quick brown fox jumps over the lazy dog. "
        "The dog slept soundly. The fox ran away quickly. "
        "A quick fox is a happy fox."
    )
    print(f"\nSimulated file content:\n  {repr(test_text)}\n")
    s2 = op.state_xition_func(s, [test_text])

    print("Transition (word-frequency analysis):")
    print(s2.jit_transition)
    print(f"\nFinal state: {s2}")
    print(f"is_goal:     {s2.is_goal()}")
    print(f"goal_message: {s2.goal_message()}")
