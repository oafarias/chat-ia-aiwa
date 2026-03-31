import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import SalaDeChat, Mensagem

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.sala_id = self.scope['url_route']['kwargs']['sala_id']
        self.room_group_name = f'chat_{self.sala_id}'

        # Entra no grupo da sala
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        mensagem_texto = data['message']
        nome_usuario = data['username']

        # Salva no banco de forma assíncrona
        await self.save_message(mensagem_texto)

        # Envia para o grupo
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': mensagem_texto,
                'username': nome_usuario
            }
        )

    async def chat_message(self, event):
        # Envia para o navegador via WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username']
        }))

    @database_sync_to_async
    def save_message(self, texto):
        sala = SalaDeChat.objects.get(id=self.sala_id)
        return Mensagem.objects.create(sala=sala, texto=texto)