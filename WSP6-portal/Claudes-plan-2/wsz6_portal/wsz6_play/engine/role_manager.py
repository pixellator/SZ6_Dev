"""
wsz6_play/engine/role_manager.py

Manages the mapping between player tokens and game roles for one session.

A *player token* is a UUID hex string issued to each connected player.
It is passed as a URL segment when the player opens the game WebSocket
(``/ws/game/<session_key>/<role_token>/``), allowing GameConsumer to
authenticate and look up the player's role number without relying on the
Django session cookie.
"""

import uuid
from typing import Dict, List, Optional


class PlayerInfo:
    """Mutable record for one connected player."""

    __slots__ = ('token', 'name', 'role_num', 'is_bot', 'user_id', 'strategy')

    def __init__(
        self,
        token: str,
        name: str,
        role_num: int = -1,
        is_bot: bool = False,
        user_id: Optional[int] = None,
        strategy: str = 'random',
    ):
        self.token    = token
        self.name     = name
        self.role_num = role_num   # -1 means unassigned
        self.is_bot   = is_bot
        self.user_id  = user_id   # Django user ID, or None for guests
        self.strategy = strategy  # bot strategy: 'random' or 'first'


class RoleManager:
    """Manages role assignments for one game session's lobby."""

    def __init__(self, roles_spec):
        """
        Args:
            roles_spec: an ``SZ_Roles_Spec`` instance from the PFF
                        (or the minimal default returned by
                        ``LobbyConsumer._default_roles_spec()``).
        """
        self.roles_spec = roles_spec
        self._players: Dict[str, PlayerInfo] = {}

    # ------------------------------------------------------------------
    # Player lifecycle
    # ------------------------------------------------------------------

    def add_player(self, name: str, user_id: Optional[int] = None) -> str:
        """Create a new player token, register the player as unassigned, and
        return the token."""
        token = uuid.uuid4().hex
        self._players[token] = PlayerInfo(token=token, name=name, user_id=user_id)
        return token

    def remove_player(self, token: str) -> None:
        self._players.pop(token, None)

    def get_player(self, token: str) -> Optional[PlayerInfo]:
        return self._players.get(token)

    # ------------------------------------------------------------------
    # Role assignment
    # ------------------------------------------------------------------

    def assign_role(self, token: str, role_num: int) -> str:
        """Assign a player to a role.

        One player per role: if the target role already has an occupant,
        that occupant is unassigned first.

        Returns:
            An error string if the assignment is invalid, otherwise ``''``.
        """
        player = self._players.get(token)
        if player is None:
            return "Unknown player token."
        roles = self.roles_spec.roles
        if not (0 <= role_num < len(roles)):
            return f"Role number {role_num} is out of range."
        # Evict current occupant of that role (skip self-assignment).
        for p in list(self._players.values()):
            if p.role_num == role_num and p.token != token:
                if p.is_bot:
                    # Bots have no browser — remove entirely when displaced.
                    del self._players[p.token]
                else:
                    p.role_num = -1
        player.role_num = role_num
        return ""

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_role_for_token(self, token: str) -> int:
        """Return role_num for a token, or -1 if unassigned / unknown."""
        p = self._players.get(token)
        return p.role_num if p else -1

    def get_token_for_role(self, role_num: int) -> Optional[str]:
        """Return the token of the player assigned to role_num, or None."""
        for p in self._players.values():
            if p.role_num == role_num:
                return p.token
        return None

    def get_all_players(self) -> List[PlayerInfo]:
        return list(self._players.values())

    def get_assigned_players(self) -> List[PlayerInfo]:
        return [p for p in self._players.values() if p.role_num >= 0]

    def is_observer_role(self, role_num: int) -> bool:
        roles = self.roles_spec.roles
        if 0 <= role_num < len(roles):
            return roles[role_num].name.lower() == 'observer'
        return False

    def count_non_observer_filled(self) -> int:
        """Return the number of distinct non-observer roles that have a player."""
        filled = {
            p.role_num
            for p in self._players.values()
            if p.role_num >= 0 and not self.is_observer_role(p.role_num)
        }
        return len(filled)

    def validate_for_start(self) -> str:
        """Return an error string if the game cannot start yet, or ``''``."""
        min_needed = getattr(self.roles_spec, 'min_players_to_start', 1)
        filled = self.count_non_observer_filled()
        if filled < min_needed:
            return (
                f"Need at least {min_needed} non-observer role(s) filled "
                f"(currently {filled})."
            )
        return ""

    def to_dict(self) -> dict:
        """Serialise for sending over WebSocket."""
        roles = self.roles_spec.roles
        return {
            'roles': [
                {
                    'role_num':    i,
                    'name':        r.name,
                    'description': r.description,
                    'is_observer': self.is_observer_role(i),
                    'player':      self._player_summary_for_role(i),
                }
                for i, r in enumerate(roles)
            ],
            'unassigned': [
                {'token': p.token, 'name': p.name}
                for p in self._players.values()
                if p.role_num < 0 and not p.is_bot
            ],
        }

    def _player_summary_for_role(self, role_num: int) -> Optional[dict]:
        token = self.get_token_for_role(role_num)
        if token is None:
            return None
        p = self._players[token]
        return {'token': p.token, 'name': p.name, 'is_bot': p.is_bot}
