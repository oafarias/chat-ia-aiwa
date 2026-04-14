from django.contrib import admin
from django.urls import path
# CORREÇÃO 1: Importar sala_chat (minúsculo) em vez de SalaDeChat (maiúsculo)
from chatconsumidor.views import index, sala_chat 
from chatatendente.views import painel, encerrar_chat

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', index, name='index'),
    
    # CORREÇÃO 2: Usar sala_chat na rota
    path('chat/<uuid:sala_id>/', sala_chat, name='sala_chat'), 
    
    path('atendimento/', painel, name='painel'),
    path('atendimento/<uuid:sala_id>/', painel, name='painel_sala'),
    path('atendimento/<uuid:sala_id>/encerrar/', encerrar_chat, name='encerrar_chat')
]