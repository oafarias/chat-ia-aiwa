import random
import uuid
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

class Fila(models.Model):
    nome = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    is_principal = models.BooleanField(default=False, verbose_name="Fila Principal")

    def save(self, *args, **kwargs):
        if self.is_principal:
            Fila.objects.filter(is_principal=True).update(is_principal=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome} {'(Principal)' if self.is_principal else ''}"

class SalaDeChat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cpf = models.CharField(max_length=14, db_index=True, null=True, blank=True) # Corrigido para CharField
    fila = models.ForeignKey(Fila, on_delete=models.SET_NULL, null=True, blank=True, related_name='salas')
    ultima_atividade = models.DateTimeField(auto_now=True)

    protocolo = models.CharField(max_length=16, unique=True, blank=True, null=True)
    cliente_nome = models.CharField(max_length=100)
    atendente = models.ForeignKey(Atendente, on_delete=models.SET_NULL, null=True, blank=True, related_name='salas')
    
    STATUS_CHOICES = [('aguardando', 'Aguardando'), ('ativo', 'Ativo'), ('encerrado', 'Encerrado')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aguardando')
    criado_em = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.protocolo:
            self.protocolo = gerar_protocolo()
        # Se a sala for nova e não tiver fila, atribui a Fila Principal
        if not self.fila:
            fila_principal = Fila.objects.filter(is_principal=True).first()
            if fila_principal:
                self.fila = fila_principal
            else:
                print("ATENÇÃO: Nenhuma Fila Principal configurada no Admin!")
                
        super().save(*args, **kwargs)

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
    atendente_escolhido = min(atendentes_disponiveis, key=lambda a: a.salas.filter(status='ativo').count())
    return atendente_escolhido