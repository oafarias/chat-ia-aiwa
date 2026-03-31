import random
from django.utils import timezone
from django.db import models
from chatatendente.models import Atendente

def gerar_protocolo():
    # Loop para garantir unicidade absoluta sem travar o servidor
    while True:
        base = timezone.now().strftime('%Y%m%d%H%M%S')
        sufixo = f"{random.randint(0, 99):02d}" # Gera de 00 a 99
        protocolo = base + sufixo
        # Só retorna se o protocolo ainda não existir no banco
        if not SalaDeChat.objects.filter(protocolo=protocolo).exists():
            return protocolo

class SalaDeChat(models.Model):
    STATUS_CHOICES = [
        ('aguardando', 'Aguardando Atendente'),
        ('ativo', 'Em Atendimento'),
        ('encerrado', 'Encerrado'),
    ]

    protocolo = models.CharField(max_length=16, unique=True, blank=True, null=True)
    cliente_nome = models.CharField(max_length=100)
    atendente = models.ForeignKey(Atendente, on_delete=models.SET_NULL, null=True, blank=True, related_name='salas')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aguardando')
    criado_em = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.protocolo:
            self.protocolo = gerar_protocolo()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.protocolo} - {self.cliente_nome}"

    class Meta:
        verbose_name="Conversa"
        verbose_name_plural="Conversas"

class Mensagem(models.Model):
    sala = models.ForeignKey(SalaDeChat, on_delete=models.CASCADE, related_name='mensagens')
    texto = models.TextField()
    # Se for nulo, a mensagem é do cliente. Se tiver valor, é do atendente.
    remetente_atendente = models.ForeignKey(Atendente, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = "Mensagem"
        verbose_name_plural = "Mensagens"

def atribuir_atendente():
    # Busca todos os atendentes online que ainda não atingiram o limite
    atendentes_disponiveis = [a for a in Atendente.objects.filter(is_online=True) if a.disponivel]
    
    if not atendentes_disponiveis:
        return None # Ninguém disponível no momento
    
    # Roteamento simples: pega quem tem MENOS chats ativos no momento (estratégia de equilíbrio)
    atendente_escolhido = min(atendentes_disponiveis, key=lambda a: a.chats_ativos)
    return atendente_escolhido