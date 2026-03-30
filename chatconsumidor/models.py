from django.db import models
from chatatendente.models import Atendente

class SalaDeChat(models.Model):
    STATUS_CHOICES = [
        ('aguardando', 'Aguardando Atendente'),
        ('ativo', 'Em Atendimento'),
        ('encerrado', 'Encerrado'),
    ]

    cliente_nome = models.CharField(max_length=100)
    atendente = models.ForeignKey(Atendente, on_delete=models.SET_NULL, null=True, blank=True, related_name='salas')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aguardando')
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat: {self.cliente_nome} - {self.status}"

class Mensagem(models.Model):
    sala = models.ForeignKey(SalaDeChat, on_delete=models.CASCADE, related_name='mensagens')
    texto = models.TextField()
    # Se for nulo, a mensagem é do cliente. Se tiver valor, é do atendente.
    remetente_atendente = models.ForeignKey(Atendente, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

def atribuir_atendente():
    # Busca todos os atendentes online que ainda não atingiram o limite
    atendentes_disponiveis = [a for a in Atendente.objects.filter(is_online=True) if a.disponivel]
    
    if not atendentes_disponiveis:
        return None # Ninguém disponível no momento
    
    # Roteamento simples: pega quem tem MENOS chats ativos no momento (estratégia de equilíbrio)
    atendente_escolhido = min(atendentes_disponiveis, key=lambda a: a.chats_ativos)
    return atendente_escolhido