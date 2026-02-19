'''sz_sessions6_02.py
ABSTRACTIONS FOR GAME ENGINES

Abstractions needed by game engines, but not needed in
problem formulations.
Status: Stubs here should be fleshed out enough to be
minimimally operational.  They can be subclassed
by the game engines.

The SZ_Solving_Session (typically representing a game play_through)
can be instantiated to get a default game
play_through in which 
a role assignment object is pre-populated with a default player
taking the role of counting-game player, but the rest of
the game play-through is empty. A game engine would normally do the 
instantiation of the game session.

 S. Tanimoto, Nov. 25, 2025
 updated Feb. 18, 2026.
 '''

import soluzion6_02 as szf # Problem-formulation abstractions

from collections import defaultdict
class SZ_Role_Assignments:
    '''Construct needed by game engines.
    Refers to roles by number within a SZ_Roles_Spec instance,
    and refers to player by strings representing session-specific
    player_ids.
    '''
    def __init__(self):
        self.role_to_player = defaultdict(list) # role_num: player_id
        self.player_to_role = defaultdict(list) # player_id: role_num
    def __str__(self):
        return f"Role Assignments: {self.role_to_player}"
    def add_player_in_role(self, player_id, role_num):
        self.role_to_player[role_num].append(player_id)
        self.player_to_role[player_id].append(role_num)
    def get_players_in_role(self, role_num):
        return self.role_to_player[role_num]
    def get_roles_of_player(self, player_id):
        return self.player_to_role[player_id]



class SZ_Solving_Session:
    ''' Encapsulates instances of needed components:
    a problem formulation, its game-instance data which can vary
    from one session to another, though not from state to
    state within a single session,
    role assignments, which include links to info about
    the players, in the general situation, but not in very
    simple games.
    This is also an abstraction for use by game engines,
    not problem formulations. '''
    def __init__(self, formulation, game_instance_data, current_state=None):
        self.formulation = formulation
        self.game_instance_data = game_instance_data
        self.role_assignments = SZ_Role_Assignments()
        self.current_state = current_state



