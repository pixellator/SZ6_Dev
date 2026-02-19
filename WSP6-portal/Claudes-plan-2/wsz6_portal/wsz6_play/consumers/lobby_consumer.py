"""
wsz6_play/consumers/lobby_consumer.py

Lobby WebSocket consumer — stub for Phase 2.
Handles session creation, player join, role assignment, and game start.
"""

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class LobbyConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.session_key = self.scope['url_route']['kwargs']['session_key']
        # TODO (Phase 2): validate session, add to group, send lobby state.
        await self.accept()
        await self.send_json({'type': 'lobby_stub', 'session_key': self.session_key})

    async def disconnect(self, close_code):
        pass

    async def receive_json(self, content):
        # TODO (Phase 2): handle join, role_select, start_game messages.
        await self.send_json({'type': 'error', 'message': 'Lobby not yet implemented.'})
