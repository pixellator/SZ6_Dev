'''Remote_LLM_Test_Game_SZ6.py

A minimal single-player test game for SOLUZION6 that exercises
remote LLM access.

The player types a free-text prompt (via a parameterized str operator).
The engine sends it to a Gemini model and shows the response as the
jit_transition message.  The player may send as many prompts as they
like, then invoke "Finish session" to end the game.

Dependencies:
    pip install google-genai

API key:
    Set the environment variable GEMINI_API_KEY before running.
    e.g.  export GEMINI_API_KEY="your-key-here"

Status: Initial SZ6 draft, Feb 2026.
'''

SOLUZION_VERSION = 6

import os

import soluzion6_02 as sz

# ---------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-2.5-flash-lite"

# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class LLM_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = "Remote LLM Test Game"
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = "1.0"
        self.authors          = ['S. Tanimoto']
        self.creation_date    = "2026-Feb"
        self.brief_desc = (
            "A minimal test that prompts a remote LLM (Gemini) and "
            "displays its response as a transition message.  The player "
            "may send multiple prompts before choosing to finish."
        )

# ---------------------------------------------------------------------------
# LLM CALL HELPER
# ---------------------------------------------------------------------------

def _make_llm_func(api_key, model_name):
    '''Return a callable(prompt_str) -> response_str that sends prompts
    to Gemini.  Raises ImportError if google.genai is not installed,
    and ValueError if the API key is missing.
    '''
    try:
        from google import genai
    except ImportError:
        raise ImportError(
            "The 'google-genai' package is required.  "
            "Install it with:  pip install google-genai"
        )
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set.  "
            "Obtain a key at https://aistudio.google.com/ and set it."
        )
    client = genai.Client(api_key=api_key)

    def call_llm(user_prompt):
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt
        )
        # The response.text might be in a different location in the new SDK
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'candidates'):
            return response.candidates[0].content.parts[0].text
        else:
            return str(response)

    return call_llm

# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class LLM_State(sz.SZ_State):
    '''
    Phases:
      'prompting' -- the player can send prompts or finish.
      'done'      -- the player invoked "Finish session"; game over.
    '''

    def __init__(self, old=None):
        if old is None:
            self.phase            = 'prompting'
            self.n_queries        = 0
            self.last_prompt      = ''
            self.last_response    = ''
            self.current_role_num = 0
        else:
            self.phase            = old.phase
            self.n_queries        = old.n_queries
            self.last_prompt      = old.last_prompt
            self.last_response    = old.last_response
            self.current_role_num = old.current_role_num

    def __str__(self):
        return self.text_view_for_role(self.current_role_num)

    def text_view_for_role(self, role_num):
        if self.phase == 'prompting':
            if self.n_queries == 0:
                return "No prompts sent yet.  Send your first prompt below."
            return (f"Queries sent so far: {self.n_queries}\n"
                    f"Last prompt:   {self.last_prompt}\n"
                    f"(LLM response was shown as transition message above.)")
        else:
            return f"Session finished.  Total queries sent: {self.n_queries}."

    def __eq__(self, s):
        return (self.phase     == s.phase and
                self.n_queries == s.n_queries and
                self.last_prompt == s.last_prompt)

    def __hash__(self):
        return hash(str(self))

    def apply_prompt(self, user_prompt, llm_func):
        '''Send user_prompt to the LLM; return a new state with the
        response stored in jit_transition.
        '''
        news              = LLM_State(old=self)
        news.last_prompt  = user_prompt
        print("  (Contacting LLM — please wait...)")
        response_text     = llm_func(user_prompt)
        news.last_response = response_text
        news.n_queries    = self.n_queries + 1
        news.jit_transition = response_text
        return news

    def apply_finish(self):
        '''Transition to the done phase.'''
        news       = LLM_State(old=self)
        news.phase = 'done'
        return news

    def is_goal(self):
        return self.phase == 'done'

    def goal_message(self):
        return (f"LLM session complete.  "
                f"Total queries sent: {self.n_queries}.")

# ---------------------------------------------------------------------------
# OPERATOR SET
# (Built inside initialize_problem so llm_func can be captured.)
# ---------------------------------------------------------------------------

def _make_operator_set(llm_func):
    '''Return a LLM_Operator_Set whose operators close over llm_func.'''

    class LLM_Operator_Set(sz.SZ_Operator_Set):
        def __init__(self):
            ask_op = sz.SZ_Operator(
                name="Send a prompt to the LLM",
                precond_func=lambda s: s.phase == 'prompting',
                state_xition_func=(
                    lambda s, args, fn=llm_func: s.apply_prompt(args[0], fn)
                ),
                params=[{
                    'name': 'prompt',
                    'type': 'str',
                }]
            )
            finish_op = sz.SZ_Operator(
                name="Finish session",
                precond_func=lambda s: (s.phase == 'prompting' and
                                        s.n_queries > 0),
                state_xition_func=lambda s: s.apply_finish(),
            )
            self.operators = [ask_op, finish_op]

    return LLM_Operator_Set()

# ---------------------------------------------------------------------------
# ROLES
# ---------------------------------------------------------------------------

class LLM_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(
                name='Prompter',
                description='Sends prompts to a remote LLM and reads responses.'),
        ]
        self.min_players_to_start = 1
        self.max_players          = 1

# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class LLM_Formulation(sz.SZ_Formulation):
    '''Top-level formulation for the Remote LLM Test Game.

    initialize_problem() reads GEMINI_API_KEY from the environment,
    constructs the LLM callable, and wires it into the operator set.
    The model name can be overridden via config['model'].
    '''

    def __init__(self):
        self.metadata    = LLM_Metadata()
        self.roles_spec  = LLM_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        self.operators   = None   # set in initialize_problem()

    def initialize_problem(self, config={}):
        api_key    = os.getenv("GEMINI_API_KEY", "")
        model_name = config.get('model', DEFAULT_MODEL)
        llm_func   = _make_llm_func(api_key, model_name)
        self.operators = _make_operator_set(llm_func)
        initial_state  = LLM_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(d={
            'initial_state': initial_state,
            'model':         model_name,
        })
        return initial_state

# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT
# ---------------------------------------------------------------------------

LLM_Game = LLM_Formulation()

# ---------------------------------------------------------------------------
# SELF-TEST  (run with: python3 Remote_LLM_Test_Game_SZ6.py)
# Requires GEMINI_API_KEY to be set.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Remote LLM Test Game SZ6 self-test ===\n")

    s = LLM_Game.initialize_problem()
    print(f"Initial state: {s}\n")

    op_ask    = LLM_Game.operators.operators[0]
    op_finish = LLM_Game.operators.operators[1]
    print(f"Operators: '{op_ask.name}', '{op_finish.name}'")
    print(f"Params:    {op_ask.params}\n")

    test_prompt = "In one sentence, what is 2 + 2 and why?"
    print(f"Sending test prompt: {repr(test_prompt)}")
    s2 = op_ask.state_xition_func(s, [test_prompt])
    print(f"\nLLM response (jit_transition):\n{s2.jit_transition}")
    print(f"\nState after query: {s2}")

    print(f"\n'Finish session' applicable: {op_finish.precond_func(s2)}")
    s3 = op_finish.state_xition_func(s2)
    print(f"Final state: {s3}")
    print(f"is_goal: {s3.is_goal()}")
    print(f"goal_message: {s3.goal_message()}")
