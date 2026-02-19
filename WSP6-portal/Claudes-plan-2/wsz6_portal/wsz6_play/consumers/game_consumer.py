"""
wsz6_play/consumers/game_consumer.py

In-game WebSocket consumer — stub for Phase 2.
Handles operator application, undo, pause, and real-time state broadcast.
"""

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class GameConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.session_key = self.scope['url_route']['kwargs']['session_key']
        self.role_token  = self.scope['url_route']['kwargs']['role_token']
        # TODO (Phase 2): authenticate role token, join group, send initial state.
        await self.accept()
        await self.send_json({'type': 'game_stub', 'session_key': self.session_key})

    async def disconnect(self, close_code):
        pass

    async def receive_json(self, content):
        # TODO (Phase 2): handle apply_operator, request_undo, request_pause.
        await self.send_json({'type': 'error', 'message': 'Game engine not yet implemented.'})

    # Channel layer message handlers (called by group_send).
    async def state_update(self, event):
        await self.send_json(event)
