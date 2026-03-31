from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # A rota usa o ID da sala para isolar as conversas
    re_path(r"ws/chat/(?P<sala_id>\d+)/$", consumers.ChatConsumer.as_asgi()),
    # Novo canal para notificações globais do atendente
    re_path(r"ws/notificacoes/$", consumers.NotificacaoConsumer.as_asgi()),
]