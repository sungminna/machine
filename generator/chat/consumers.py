from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        try:
            pass
        except Exception as e:
            await self.close()


    async def disconnect(self, code):
        pass
