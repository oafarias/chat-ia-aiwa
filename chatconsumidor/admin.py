from django.contrib import admin
from django.utils.html import format_html
import json
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

@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ('id', 'sala', 'remetente_atendente', 'timestamp', 'tem_metadados')
    list_filter = ('timestamp', ('remetente_atendente', admin.RelatedOnlyFieldListFilter))
    
    # Colocamos o campo raciocinio_ia_formatado como somente leitura
    readonly_fields = ('raciocinio_ia_formatado',)
    
    # Esconde o campo JSON original feio e mostra apenas o formatado
    exclude = ('ai_metadata',)

    def tem_metadados(self, obj):
        """Retorna um ícone de 'check' verde no admin se a mensagem tiver raciocínio da IA"""
        return bool(obj.ai_metadata)
    tem_metadados.boolean = True
    tem_metadados.short_description = "IA Pensou?"

    def raciocinio_ia_formatado(self, obj):
        """Formata o JSON em um bloco de código bonitinho no painel do Admin"""
        if obj.ai_metadata:
            # Transforma o dicionário em um JSON com indentação e quebras de linha
            json_formatado = json.dumps(obj.ai_metadata, indent=4, ensure_ascii=False)
            # Retorna um HTML com a tag <pre> para respeitar os espaços
            return format_html(
                '<pre style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap;">{}</pre>', 
                json_formatado
            )
        return "Sem metadados gerados."
    raciocinio_ia_formatado.short_description = "Raciocínio Interno da IA"