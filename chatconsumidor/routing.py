from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # A rota usa UUID para reduzir risco de enumeração de salas
    re_path(r"ws/chat/(?P<sala_id>[0-9a-fA-F-]{36})/$", consumers.ChatConsumer.as_asgi()),
    # Novo canal para notificações globais do atendente
    re_path(r"ws/notificacoes/$", consumers.NotificacaoConsumer.as_asgi()),
]