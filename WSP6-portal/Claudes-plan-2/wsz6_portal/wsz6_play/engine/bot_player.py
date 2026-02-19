"""
wsz6_play/engine/bot_player.py

Automatic bot player that applies operators on behalf of a role.

A BotPlayer is stored in session['bots'] and checked by GameConsumer after
every state change.  If it is the bot's turn, maybe_move() picks an operator
and applies it through the normal GameRunner path (so it is logged and
broadcast identically to a human move).

Strategies
----------
'random'  — pick a random applicable operator (default).
'first'   — pick the first applicable operator by index.
"""

import asyncio
import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)


class BotPlayer:
    """Async bot that plays one role in a game session."""

    def __init__(
        self,
        role_num:  int,
        strategy:  str   = 'random',
        delay:     float = 1.2,
    ):
        """
        Args:
            role_num:  The role number this bot plays.
            strategy:  'random' or 'first'.
            delay:     Seconds to pause before playing (simulates thinking).
        """
        self.role_num = role_num
        self.strategy = strategy
        self.delay    = delay

    async def maybe_move(self, runner, current_role_num: int) -> Optional[int]:
        """If it is this bot's turn, pick and apply an operator.

        Args:
            runner:           The active GameRunner.
            current_role_num: The role whose turn it currently is.

        Returns:
            The op_index that was applied, or None if the bot did not move
            (not its turn, game over, or no applicable operators).
        """
        if current_role_num != self.role_num:
            return None
        if runner.finished:
            return None

        ops = runner.get_ops_info(runner.current_state)
        applicable = [
            op for op in ops
            if op['applicable'] and op.get('role') in (None, self.role_num)
        ]
        if not applicable:
            logger.warning(
                "BotPlayer role=%d: no applicable operators at step %d",
                self.role_num, runner.step,
            )
            return None

        chosen = (
            random.choice(applicable)
            if self.strategy == 'random'
            else applicable[0]
        )

        await asyncio.sleep(self.delay)
        await runner.apply_operator(chosen['index'])
        return chosen['index']
