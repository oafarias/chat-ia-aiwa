import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import SalaDeChat, Mensagem
from chatatendente.models import Atendente
from django.contrib.auth.models import User

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
        if not getattr(self, 'is_intentional_close', False):
            query_string = self.scope.get('query_string', b'').decode('utf-8')
            is_consumer_page = 'tipo=consumidor' in query_string
            por_quem = 'rede_consumidor' if is_consumer_page else 'rede_atendente'
            await self.set_sala_encerrada(por_quem)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_ended',
                    'por_quem': por_quem
                }
            )
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'close_chat':
            self.is_intentional_close = True
            query_string = self.scope.get('query_string', b'').decode('utf-8')
            is_consumer_page = 'tipo=consumidor' in query_string
            por_quem = 'consumidor' if is_consumer_page else 'atendente'
            await self.set_sala_encerrada(por_quem)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_ended',
                    'por_quem': por_quem
                }
            )
            return

        mensagem_texto = data.get('message', '').strip()
        if not mensagem_texto:
            return

        identidade = await self.resolve_sender_identity()
        if not identidade:
            await self.close(code=4003)
            return

        # Salva no banco usando a identidade validada no backend
        message_saved = await self.save_message(mensagem_texto, identidade['remetente_id'])
        if not message_saved:
            await self.close(code=4004)
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': mensagem_texto,
                'username': identidade['username']
            }
        )

        # Atualiza o painel do atendente sobre nova mensagem
        await self.channel_layer.group_send(
            'notificacoes',
            {
                'type': 'notify',
                'event_type': 'nova_mensagem',
                'message': f"Nova mensagem de {identidade['username']}",
                'sala_id': str(self.sala_id)
            }
        )

        # === NOVA LÓGICA DA IA (TRIAGEM E RESPOSTA) ===
        # Se remetente_id for None, quem falou foi o consumidor.
        if identidade['remetente_id'] is None:
            precisa_de_ia = await self.verificar_triagem_ia()
            
            if precisa_de_ia:
                # Lança a IA em segundo plano, liberando a tela na mesma hora
                asyncio.create_task(self.responder_com_ia(mensagem_texto))

    async def responder_com_ia(self, mensagem_texto):
        from chatai.services import perguntar_a_ia_stream
        
        # 1. Envia sinal para o frontend mostrar as bolinhas de "digitando..."
        await self.send(text_data=json.dumps({'action': 'typing_start'}))

        texto_completo = ""

        # 2. Escuta o fluxo contínuo de caracteres
        async for chunk in perguntar_a_ia_stream(mensagem_texto):
            texto_completo += chunk
            # Envia pedaço a pedaço
            await self.send(text_data=json.dumps({
                'action': 'stream_chunk',
                'message': chunk,
                'username': 'Assistente Virtual'
            }))

        # 3. Fecha o balão de mensagem no frontend
        await self.send(text_data=json.dumps({'action': 'stream_end'}))
        
        # 4. Salva a versão inteira e consolidada no banco de dados 
        await self.salvar_mensagem_ia(texto_completo)

    async def chat_message(self, event):
        # Envia a mensagem para o WebSocket (Consumidor ou Atendente)
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username']
        }))

    async def chat_ended(self, event):
        await self.send(text_data=json.dumps({
            'action': 'chat_ended',
            'por_quem': event['por_quem']
        }))
        self.is_intentional_close = True
        await self.close()

    @database_sync_to_async
    def set_sala_encerrada(self, por_quem):
        try:
            sala = SalaDeChat.objects.get(id=self.sala_id)
            if sala.status != 'encerrado':
                sala.status = 'encerrado'
                sala.encerrado_por = por_quem
                sala.save()
        except SalaDeChat.DoesNotExist:
            pass

    @database_sync_to_async
    def sala_exists(self):
        return SalaDeChat.objects.filter(id=self.sala_id).exists()

    @database_sync_to_async
    def resolve_sender_identity(self):
        try:
            sala = SalaDeChat.objects.select_related('atendente__user').get(id=self.sala_id)
        except SalaDeChat.DoesNotExist:
            return None

        user = self.scope.get('user')
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        is_consumer_page = 'tipo=consumidor' in query_string

        if user and user.is_authenticated and not is_consumer_page:
            try:
                perfil_atendente = Atendente.objects.select_related('user').get(user=user)
            except Atendente.DoesNotExist:
                return {
                    'username': sala.cliente_nome,
                    'remetente_id': None,
                }

            # Apenas o atendente vinculado a sala pode escrever como atendente.
            if sala.atendente_id != perfil_atendente.id:
                return None

            return {
                'username': perfil_atendente.user.get_username(),
                'remetente_id': perfil_atendente.id,
            }

        return {
            'username': sala.cliente_nome,
            'remetente_id': None,
        }

    @database_sync_to_async
    def save_message(self, texto, remetente_id):
        try:
            sala = SalaDeChat.objects.get(id=self.sala_id)
        except SalaDeChat.DoesNotExist:
            return None

        remetente = Atendente.objects.filter(id=remetente_id).first() if remetente_id else None

        Mensagem.objects.create(
            sala=sala, 
            texto=texto, 
            remetente_atendente=remetente
        )
        return True
    
    @database_sync_to_async
    def verificar_triagem_ia(self):
        try:
            # select_related para evitar queries extras ao buscar o username
            sala = SalaDeChat.objects.select_related('atendente__user').get(id=self.sala_id)
            
            # A IA entra em ação se:
            # 1. A sala ainda não tem atendente (órfã)
            # 2. OU a sala foi atribuída ao próprio Bot da IA
            if sala.atendente is None:
                return True
                
            if sala.atendente.user.username == "Assistente_IA":
                return True
                
            return False 
        except SalaDeChat.DoesNotExist:
            return False

    @database_sync_to_async
    def salvar_mensagem_ia(self, texto):
        try:
            sala = SalaDeChat.objects.get(id=self.sala_id)
            
            # Cria um "Atendente Fantasma" no banco silenciosamente se ele não existir
            user_bot, _ = User.objects.get_or_create(
                username="Assistente_IA", 
                defaults={"first_name": "Assistente Virtual"}
            )
            atendente_bot, _ = Atendente.objects.get_or_create(
                user=user_bot, 
                defaults={"is_online": True, "max_chats": 9999}
            )
            
            Mensagem.objects.create(
                sala=sala, 
                texto=texto, 
                remetente_atendente=atendente_bot
            )
            return user_bot.first_name
        except Exception as e:
            print(f"Curto-circuito ao salvar msg da IA: {e}")
            return "Assistente"


class NotificacaoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add('notificacoes', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('notificacoes', self.channel_name)

    async def notify(self, event):
        await self.send(text_data=json.dumps({
            'message': event.get('message', ''),
            'type': event.get('event_type', 'notificacao'),
            'sala_id': event.get('sala_id', None)
        }))