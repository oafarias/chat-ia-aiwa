from django.db import models
from django.contrib.auth.models import User

class Atendente(models.Model):
    # Conecta esse perfil ao usuário de login do Django
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_atendente')
    
    # Controles de roteamento
    is_online = models.BooleanField(default=False)
    max_chats = models.IntegerField(default=3)
    chats_ativos = models.IntegerField(default=0)

    @property
    def disponivel(self):
        # Essa é a regra de ouro que o roteador vai olhar antes de enviar um chat
        ativos = self.salas.filter(status='ativo').count()
        return self.is_online and ativos < self.max_chats

    def __str__(self):
        status = "🟢 Online" if self.is_online else "🔴 Offline"
        ativos = self.salas.filter(status='ativo').count() if self.pk else 0
        return f"{self.user.username} | {status} | Chats: {ativos}/{self.max_chats}"