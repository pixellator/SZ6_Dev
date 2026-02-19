"""
wsz6_play/consumers/echo_consumer.py

Phase 0 WebSocket echo consumer.

Connects to ws://localhost:8000/ws/echo/ and echoes back every
JSON message it receives, adding an "echo": true field.

Used solely to verify that the Django Channels stack (ASGI server +
channel layer) is wired up correctly before any game logic is added.
"""

import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class EchoConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        await self.accept()
        await self.send_json({
            'type': 'connected',
            'message': 'WSZ6 WebSocket echo server ready.',
        })

    async def disconnect(self, close_code):
        pass   # Nothing to clean up in the echo consumer.

    async def receive_json(self, content):
        """Echo the message back with an extra field."""
        content['echo'] = True
        await self.send_json(content)
