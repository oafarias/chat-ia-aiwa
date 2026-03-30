from django.contrib import admin
from .models import Atendente

@admin.register(Atendente)
class AtendenteAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_online', 'chats_ativos', 'max_chats', 'disponivel')
    list_editable = ('is_online', 'max_chats') 
    list_filter = ('is_online',)
    