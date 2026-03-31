from django.contrib import admin
from .models import SalaDeChat, Mensagem

# 1. Cria a estrutura da tabela de mensagens para ser embutida
class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0 # Não exibe linhas vazias extras
    readonly_fields = ('remetente_atendente', 'texto', 'timestamp')
    can_delete = False # Segurança: impede apagar mensagens individuais do histórico
    
    # Remove o botão de "Adicionar nova mensagem" por dentro do admin
    def has_add_permission(self, request, obj=None):
        return False

# 2. Registra a Sala (agora "Conversas") com as mensagens embutidas
@admin.register(SalaDeChat)
class SalaDeChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente_nome', 'atendente', 'status', 'criado_em')
    list_filter = ('status', 'atendente')
    search_fields = ('cliente_nome',)
    
    # Aqui é onde a mágica acontece:
    inlines = [MensagemInline]