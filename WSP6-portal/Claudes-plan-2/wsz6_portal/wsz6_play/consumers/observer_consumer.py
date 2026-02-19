"""
wsz6_play/consumers/observer_consumer.py

Observer WebSocket consumer — stub for Phase 4.
Allows admins to watch (or join) live game sessions.
"""

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ObserverConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.session_key = self.scope['url_route']['kwargs']['session_key']
        # TODO (Phase 4): verify admin permissions, join group.
        await self.accept()
        await self.send_json({'type': 'observer_stub', 'session_key': self.session_key})

    async def disconnect(self, close_code):
        pass

    async def receive_json(self, content):
        # TODO (Phase 4): handle perspective_switch, take_role.
        await self.send_json({'type': 'error', 'message': 'Observer not yet implemented.'})

    async def state_update(self, event):
        await self.send_json(event)
