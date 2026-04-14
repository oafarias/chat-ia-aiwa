from django.contrib import admin
from .models import SalaDeChat, Mensagem, Fila

# 1. Cria a estrutura da tabela de mensagens para ser embutida
class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0 # Não exibe linhas vazias extras
    readonly_fields = ('remetente_atendente', 'texto', 'timestamp')
    can_delete = False # Segurança: impede apagar mensagens individuais do histórico
    
    # Remove o botão de "Adicionar nova mensagem" por dentro do admin
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Fila)
class FilaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'is_principal')
    prepopulated_fields = {'slug': ('nome',)}

# 2. Registra a Sala (agora "Conversas") com as mensagens embutidas
@admin.register(SalaDeChat)
class SalaDeChatAdmin(admin.ModelAdmin):
    list_display = ('protocolo', 'cliente_nome', 'cpf', 'atendente', 'status', 'criado_em')
    list_filter = ('status', 'fila')
    search_fields = ('protocolo', 'cliente_nome')
    
    # Aqui é onde a mágica acontece:
    inlines = [MensagemInline]