'''soluzion6_02.py
Operational version of soluzion6_01.py, which only provided stubs for
the class definitions.
Although each class here is intended to be subclassed in any useful
new problem formulation, all classes here can be instantiated
directly and the default game will be a "counting game" with initial
state 0, one operator called "Next", and one role called "counting-game player".

Updated Nov 25, 2025.  S. Tanimoto.
Ready to be tested with a new bare-bones textual game engine.
'''



class SZ_Metadata:
    '''A component of a formulation'''
    def __init__(self):
        self.name = "Base Problem/Game"
        self.authoring_date = "2025-Nov-25"
        self.brief_desc = "Counting game"

class SZ_Common_Data:
    '''Data common not only to all states of a session but
    all games in the family.'''
    def __init__(self):
        pass

class SZ_Problem_Instance_Data:
    '''Data particular to the current problem/game session, that
    specifies this problem/game instance within the family.
    E.g., the number of disks in a Towers of Hanoi puzzle,
    or the shuffling and dealing of the cards in Clue.'''
    def __init__(self, d={}):
        self.data = d

class SZ_State:
    '''Prototype state for puzzles and games, with defaults
    for common methods such as deep copying, __str__, 
    __eq__, __hash__, can_move, move, is_goal, is_win,
    and possibly others.'''
    def __init__(self, old=None, initial_value=None):
        if old is not None:
            # Copy constructor
            self.value = old.value
        else:
            self.value = initial_value  # Default initial value

    def copy_and_increment(self, amount):
        new_state = SZ_State(old=self)
        new_state.value += amount
        return new_state

class SZ_Operator:
    '''General operator class supporting as subclass(es) parameterized
    operators. Default names and descriptions are generated using an opcount
    class variable.  There is a default precondition function that always returns True.'''

    opcount = 0
    def __init__(self,
                 name="op"+str(opcount),
                 description="Operator number "+str(opcount),
                 precond_func=lambda state: True,
                 state_xition_func=None,
                 params=[],
                 role=None):
        self.name = name
        self.description = description
        self.precond_func = precond_func
        self.state_xition_func = state_xition_func
        self.params = params  # List of param-spec dicts; empty for non-parameterized ops.
        self.role = role  # Role number this op belongs to, or None if unrestricted.
        SZ_Operator.opcount += 1

# To do: Implement special precondition function called "try_xition_func"
# that attempts to apply the state transition function, within a Try-Except
# block, returning False if an exception occurs, and True otherwise.
# When True, the new state is saved in the "cached_new_state" array (indexed
# by operator numbers) in a game engine, in the array location associated
# with the current operator.  Then, if and when the operator is actually applied,
# the cached new state is retrieved and used as the new state.
# The apply method will first check for the presence of a cached new state,
# and if found, will use it directly, otherwise it will call the state transition function.
# This approach allows operators that may fail to be tried without raising exceptions
# that would interfere with the game engine's operation.
# Note that try_xition_func would not be appropriate with parameterized operators.

class SZ_Operator_Set:
    '''Collection of operators. 
    Instantiated in a Problem formulation.
    This abstraction supports meta-problem-space
    exploration.'''
    
    # This operator is needed only for the default counting game formulation:
    next_number_operator = SZ_Operator(
        name="Next",
        description="Increments the current number by 1",
        state_xition_func=lambda state: state.copy_and_increment(1)
    )

    def __init__(self):
        self.operators = [SZ_Operator_Set.next_number_operator]


class SZ_Role:
    '''A role in a problem/game formulation.'''
    def __init__(self, name="default-role", description="A default role"):
        self.name = name
        self.description = description

class SZ_Roles_Spec:
    '''Methods for specifying roles.'''
    def __init__(self):
        self.roles = [SZ_Role()]  #name="Incrementer", description="counting-game player")]
        # Note, the more specific name and desc. are not being used here, since we want generic roles
        # to be the defaults in this base implementation.

class SZ_Formulation:
    '''An encapsulation of a problem/game formulation, which specifies a family of 
    one or more games; e.g., the Towers of Hanoi, which can have different numbers
    of disks, and thus having N_DISKS as a session-creation parameter.'''
    
    def __init__(self, metadata=SZ_Metadata(), common_data=SZ_Common_Data(), operators=SZ_Operator_Set()):
        self.metadata = metadata
        self.common_data = common_data
        self.operators = operators

    def initialize_problem(self):
        '''Performs retrieval of problem/game configuration
        parameters, if needed (by calling game engine method),
        and then setting up the problem instance data, and
        finally creating the initial state. '''

        starting_value = 0  # In a real implementation, retrieve from game engine 
        initial_state = SZ_State(initial_value=starting_value)
        self.instance_data = SZ_Problem_Instance_Data(d={'starting_value':starting_value, 'initial_state':initial_state})


def test():
    '''Simple test of the counting game formulation.'''
    formulation = SZ_Formulation()
    formulation.initialize_problem()
    initial_state = formulation.instance_data.data['initial_state']
    print("Initial state value:", initial_state.value)
    operator = formulation.operators.operators[0]  # The "Next" operator
    new_state = operator.state_xition_func(initial_state)
    print("New state value after applying operator:", new_state.value)  

if __name__ == "__main__":
    test()  

