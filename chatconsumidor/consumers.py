import json
import asyncio
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import SalaDeChat, Mensagem, Fila
from chatatendente.models import Atendente
from django.contrib.auth.models import User

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.sala_id = self.scope['url_route']['kwargs']['sala_id']
        self.room_group_name = f'chat_{self.sala_id}'
        
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        self.estado_timeout = 'normal' # Inicia o estado da Máquina
        self.ultima_atividade = timezone.now()
        self.timeout_task = asyncio.create_task(self.verificar_timeout())

        na_fila_ia = await self.is_na_fila_ia()
        sala_vazia = await self.is_room_empty()
        
        print(f"DEBUG: Conectado! Sala: {self.sala_id} | Fila IA: {na_fila_ia} | Vazia: {sala_vazia}", flush=True)

        if na_fila_ia and sala_vazia:
            await asyncio.sleep(1)
            asyncio.create_task(self.responder_com_ia(self.sala_id))

    @database_sync_to_async
    def is_na_fila_ia(self):
        try:
            sala = SalaDeChat.objects.select_related('fila').get(id=self.sala_id)
            return sala.fila and (sala.fila.slug == 'ia' or sala.fila.slug == 'triagem-ia')
        except:
            return False

    @database_sync_to_async
    def is_room_empty(self):
        return not Mensagem.objects.filter(sala_id=self.sala_id).exists()

    async def verificar_timeout(self):
        """Máquina de Estados de Timeout: 2 min (Aviso) -> 1 min (Fechamento)"""
        timeout_aviso = 2 
        timeout_encerramento = 1  # Agora é 1 minuto DEPOIS do aviso

        try:
            while True:
                await asyncio.sleep(10)
                tempo_ocioso = (timezone.now() - self.ultima_atividade).total_seconds() / 60
                
                if self.estado_timeout == 'normal':
                    # Fase 1: Chat ocioso atingiu 2 minutos
                    if tempo_ocioso >= timeout_aviso:
                        self.estado_timeout = 'gerando_aviso'
                        
                        msg_oculta_sistema = "[SISTEMA]: O cliente não responde há 2 minutos. Analise o assunto do chat atual e envie uma mensagem educada, avisando que o chat será encerrado em 1 minuto caso ele não retorne. Caso o cliente precise de mais tempo para realizar algum teste informe que o chat pode ser finalizado e quando ele retornar basta digitar o CPF novamente que retomamos o assunto de onde paramos."
                        
                        task = asyncio.create_task(self.enviar_aviso_ia(self.sala_id, msg_oculta_sistema))
                        if not hasattr(self, 'background_tasks'):
                            self.background_tasks = set()
                        self.background_tasks.add(task)
                        task.add_done_callback(self.background_tasks.discard)

                elif self.estado_timeout == 'aguardando_fechamento':
                    # Fase 2: O aviso já foi enviado. Espera 1 minuto extra para fechar.
                    if tempo_ocioso >= timeout_encerramento:
                        msg_final = "Chat finalizado por inatividade. Caso deseje retornar, basta acessar nossa página e informar seu CPF novamente. Continuaremos o atendimento de onde paramos! 👋"
                        
                        await self.salvar_mensagem_ia(msg_final)
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'chat_message',
                                'message': msg_final,
                                'username': 'Assistente Virtual'
                            }
                        )
                        
                        await self.set_sala_encerrada('timeout_sistema')
                        
                        # --- DISPARA A AÇÃO "FINALIZANDO" PARA BLOQUEAR O INPUT ---
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'chat_finalizing'
                            }
                        )
                        
                        # Aguarda 10 segundos antes de disparar o encerramento no front-end
                        await asyncio.sleep(10) 
                        
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'chat_ended',
                                'por_quem': 'timeout_sistema'
                            }
                        )
                        break
        except asyncio.CancelledError:
            pass

    async def enviar_aviso_ia(self, sala_id, msg):
        """Orquestra o envio do aviso e avança a Máquina de Estados"""
        await self.responder_com_ia(sala_id, mensagem_sistema=msg)
        
        # Se o usuário não enviou mensagem enquanto a IA digitava o aviso, 
        # avançamos para o estágio final (contagem regressiva para morrer).
        if getattr(self, 'estado_timeout', '') == 'gerando_aviso':
            self.estado_timeout = 'aguardando_fechamento'

    async def disconnect(self, close_code):
        if hasattr(self, 'timeout_task'):
            self.timeout_task.cancel()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        # AÇÃO DO USUÁRIO: Zera o relógio E volta o chat pro estado normal (cancela encerramento)
        self.ultima_atividade = timezone.now()
        self.estado_timeout = 'normal'

        data = json.loads(text_data)
        action = data.get('action')

        if action == 'transferir_fila':
            nova_fila_id = data.get('fila_id')
            await self.mudar_fila(nova_fila_id)
            return
        
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

        await self.channel_layer.group_send(
            'notificacoes',
            {
                'type': 'notify',
                'event_type': 'nova_mensagem',
                'message': f"Nova mensagem de {identidade['username']}",
                'sala_id': str(self.sala_id)
            }
        )

        if identidade['remetente_id'] is None:
            precisa_de_ia = await self.verificar_triagem_ia()
            
            if precisa_de_ia:
                task = asyncio.create_task(self.responder_com_ia(self.sala_id))
                
                if not hasattr(self, 'background_tasks'):
                    self.background_tasks = set()
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)

    async def responder_com_ia(self, sala_id, mensagem_sistema=None):
        from chatai.services import perguntar_a_ia_stream
        
        await self.send(text_data=json.dumps({'action': 'typing_start'}))
        texto_completo = ""
        metadata_ia = {}

        # Passa a nossa instrução fantasma pro Gemini
        async for chunk in perguntar_a_ia_stream(sala_id, meta_out=metadata_ia, mensagem_sistema=mensagem_sistema):
            texto_completo += chunk
            await self.send(text_data=json.dumps({
                'action': 'stream_chunk',
                'message': chunk,
                'username': 'Assistente Virtual'
            }))

        await self.send(text_data=json.dumps({'action': 'stream_end'}))
        
        await self.salvar_mensagem_ia(texto_completo, ai_metadata=metadata_ia)
        
        # Após a IA responder, o relógio é zerado valendo!
        self.ultima_atividade = timezone.now()

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username']
        }))

    # NOVO: Função que propaga a ação de bloqueio pro JS do cliente
    async def chat_finalizing(self, event):
        await self.send(text_data=json.dumps({
            'action': 'finalizando'
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
                return {'username': sala.cliente_nome, 'remetente_id': None}

            if sala.atendente_id != perfil_atendente.id:
                return None

            return {'username': perfil_atendente.user.get_username(), 'remetente_id': perfil_atendente.id}

        return {'username': sala.cliente_nome, 'remetente_id': None}
    
    @database_sync_to_async
    def mudar_fila(self, fila_id):
        try:
            sala = SalaDeChat.objects.get(id=self.sala_id)
            nova_fila = Fila.objects.get(id=fila_id)
            sala.fila = nova_fila
            sala.save()
        except Exception as e:
            pass

    @database_sync_to_async
    def save_message(self, texto, remetente_id):
        try:
            sala = SalaDeChat.objects.get(id=self.sala_id)
        except SalaDeChat.DoesNotExist:
            return None

        remetente = Atendente.objects.filter(id=remetente_id).first() if remetente_id else None
        Mensagem.objects.create(sala=sala, texto=texto, remetente_atendente=remetente)
        return True
    
    @database_sync_to_async
    def verificar_triagem_ia(self):
        try:
            sala = SalaDeChat.objects.select_related('atendente__user').get(id=self.sala_id)
            if sala.atendente is None or sala.atendente.user.username == "Assistente_IA":
                return True
            return False 
        except SalaDeChat.DoesNotExist:
            return False

    @database_sync_to_async
    def salvar_mensagem_ia(self, texto, ai_metadata=None):
        try:
            sala = SalaDeChat.objects.get(id=self.sala_id)
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
                remetente_atendente=atendente_bot,
                ai_metadata=ai_metadata
            )
            return user_bot.first_name
        except Exception as e:
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