from django.db import models

class ConfiguracaoIA(models.Model):
    PROVEDORES = [
        ('openai', 'OpenAI (ChatGPT)'),
        ('gemini', 'Google Gemini'),
        ('claude', 'Anthropic (Claude)'),
    ]

    nome = models.CharField(max_length=50, help_text="Ex: Bot de Vendas Agressivo")
    provedor = models.CharField(max_length=20, choices=PROVEDORES, default='openai')
    modelo = models.CharField(
        max_length=100, 
        default='gpt-4o-mini', 
        help_text="Digite o nome exato da API. Dicas: 'gpt-4o', 'gpt-4o-mini', 'gemini-2.5-flash', 'gemini-1.5-pro', 'claude-3-5-sonnet-20241022'."
    )
    api_key = models.CharField(max_length=255)
    system_prompt = models.TextField(help_text="A personalidade e regras da IA", default="Você é um assistente prestativo.")
    is_active = models.BooleanField(default=False, verbose_name="Ativo?")

    token_telecontrol = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Token da API Telecontrol (access-application-key)"
    )

    # ... resto do código ...

    def save(self, *args, **kwargs):
        if self.is_active:
            # Desativa as outras configurações para manter apenas uma "no comando"
            ConfiguracaoIA.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        status = "🟢 ATIVO" if self.is_active else "🔴 Inativo"
        return f"{self.nome} ({self.get_provedor_display()} | {self.modelo}) - {status}"

    class Meta:
        verbose_name = "Configuração de IA"
        verbose_name_plural = "Configurações de IA"