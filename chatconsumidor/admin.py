from django.contrib import admin
from django.contrib import messages
from django.utils.html import escape
from django.utils.safestring import mark_safe
import json
import re
from .models import SalaDeChat, Mensagem, Fila

class MensagemInline(admin.StackedInline):
    model = Mensagem
    extra = 0 
    readonly_fields = ('remetente_atendente', 'texto', 'timestamp', 'raciocinio_ia_formatado')
    exclude = ('ai_metadata',) 
    can_delete = False 
    
    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Raciocínio Interno da IA")
    def raciocinio_ia_formatado(self, obj):
        if not obj.ai_metadata:
            return "Sem metadados gerados."

        # Validação de segurança: caso o Django tenha salvo como String ao invés de Dict
        metadata = obj.ai_metadata
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {"Dados Brutos": metadata}

        # Criação do HTML blindado
        html_parts = ['<div style="background-color: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; border-radius: 6px; box-shadow: inset 0 1px 2px rgba(0,0,0,.05);">']

        for key, value in metadata.items():
            key_formatted = escape(str(key).replace('_', ' ').title())
            
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, indent=4, ensure_ascii=False)
                value_html = f"<pre style='margin: 0; white-space: pre-wrap; font-family: monospace; background: #fff; padding: 12px; border-radius: 4px; border: 1px solid #e9ecef; font-size: 13px;'>{escape(value_str)}</pre>"
            else:
                val_str = escape(str(value))
                
                # Regex Seguro para Markdown (captura espaços e quebras de linha com .*?)
                val_str = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', val_str, flags=re.DOTALL)
                val_str = re.sub(r'\*(.*?)\*', r'<em>\1</em>', val_str, flags=re.DOTALL)
                val_str = re.sub(r'`(.*?)`', r'<code style="background-color: #e9ecef; padding: 2px 5px; border-radius: 4px; font-family: monospace; color: #d63384; font-size: 12px;">\1</code>', val_str, flags=re.DOTALL)
                
                value_html = f"<div style='white-space: pre-wrap; line-height: 1.6; font-size: 14px; color: #212529; background-color: #fff; padding: 15px; border: 1px solid #e9ecef; border-radius: 4px;'>{val_str}</div>"

            html_parts.append(f"<div style='margin-bottom: 20px;'><h4 style='margin: 0 0 8px 0; color: #495057; font-size: 13px; text-transform: uppercase; border-bottom: 2px solid #e9ecef; padding-bottom: 5px;'>{key_formatted}</h4>{value_html}</div>")
        
        html_parts.append('</div>')
        return mark_safe("".join(html_parts))

@admin.register(Fila)
class FilaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'is_principal')
    prepopulated_fields = {'slug': ('nome',)}

@admin.register(SalaDeChat)
class SalaDeChatAdmin(admin.ModelAdmin):
    list_display = ('protocolo', 'cliente_nome', 'cpf', 'atendente', 'status', 'criado_em')
    list_filter = ('status', 'fila')
    search_fields = ('protocolo', 'cliente_nome', 'cpf')
    readonly_fields = ('id', 'protocolo', 'cliente_nome', 'cpf', 'criado_em')
    
    inlines = [MensagemInline]

    ordering = ('-criado_em',)  
    list_per_page = 50          
    actions = ['finalizar_conversa']

    @admin.action(description='Finalizar conversas selecionadas')
    def finalizar_conversa(self, request, queryset):
        atualizados = queryset.update(status='encerrado')
        self.message_user(
            request, 
            f'{atualizados} conversa(s) foi/foram finalizada(s) com sucesso.', 
            messages.SUCCESS
        )

    def has_add_permission(self, request):
        return False

@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ('id', 'sala', 'remetente_atendente', 'timestamp', 'tem_metadados')
    list_filter = ('timestamp', ('remetente_atendente', admin.RelatedOnlyFieldListFilter))
    readonly_fields = ('raciocinio_ia_formatado',)
    exclude = ('ai_metadata',)

    def tem_metadados(self, obj):
        return bool(obj.ai_metadata)
    tem_metadados.boolean = True
    tem_metadados.short_description = "IA Pensou?"

    @admin.display(description="Raciocínio Interno da IA")
    def raciocinio_ia_formatado(self, obj):
        # Chama a mesma função que está no Inline para não duplicar código!
        inline = MensagemInline(self.model, self.admin_site)
        return inline.raciocinio_ia_formatado(obj)