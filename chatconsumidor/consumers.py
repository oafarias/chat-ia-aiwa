import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import SalaDeChat, Mensagem

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.sala_id = self.scope['url_route']['kwargs']['sala_id']
        self.room_group_name = f'chat_{self.sala_id}'

        # Evita abrir conexao para salas inexistentes
        sala_existe = await self.sala_exists()
        if not sala_existe:
            await self.close(code=4004)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        mensagem_texto = data.get('message', '').strip()
        nome_usuario = data.get('username', '').strip()

        if not mensagem_texto or not nome_usuario:
            return

        # Salva no banco identificando se é atendente ou não
        message_saved = await self.save_message(mensagem_texto, nome_usuario)
        if not message_saved:
            await self.close(code=4004)
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': mensagem_texto,
                'username': nome_usuario
            }
        )

    async def chat_message(self, event):
        # Envia a mensagem para o WebSocket (Consumidor ou Atendente)
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username']
        }))

    @database_sync_to_async
    def sala_exists(self):
        return SalaDeChat.objects.filter(id=self.sala_id).exists()

    @database_sync_to_async
    def save_message(self, texto, username):
        try:
            sala = SalaDeChat.objects.get(id=self.sala_id)
        except SalaDeChat.DoesNotExist:
            return None

        remetente = None
        
        # Se o nome for o do atendente, vinculamos o perfil dele à mensagem
        if username == "Atendente AIWA":
            remetente = sala.atendente
            
        Mensagem.objects.create(
            sala=sala, 
            texto=texto, 
            remetente_atendente=remetente
        )
        return True


class NotificacaoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add('notificacoes', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('notificacoes', self.channel_name)

    async def notify(self, event):
        await self.send(text_data=json.dumps({
            'message': event.get('message', ''),
            'type': event.get('event_type', 'notificacao')
        }))