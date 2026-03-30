from django.contrib import admin
from .models import SalaDeChat, Mensagem # O ponto é essencial aqui

@admin.register(SalaDeChat)
class SalaDeChatAdmin(admin.ModelAdmin):
    list_display = ('cliente_nome', 'atendente', 'status', 'criado_em')
    list_filter = ('status', 'atendente')
    search_fields = ('cliente_nome',)

@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ('sala', 'remetente_atendente', 'texto', 'timestamp')
    list_filter = ('timestamp',)