import openai
import anthropic
from django.contrib import admin
from django.contrib import messages
from .models import ConfiguracaoIA
from google import genai
from google.genai import types

@admin.register(ConfiguracaoIA)
class ConfiguracaoIAAdmin(admin.ModelAdmin):
    list_display = ('nome', 'provedor', 'modelo', 'is_active')
    list_filter = ('provedor', 'is_active')
    
    # Organizando visualmente os campos na tela de edição do Admin
    fieldsets = (
        ('Informações Principais', {
            'fields': ('nome', 'is_active')
        }),
        ('Motor da IA', {
            'fields': ('provedor', 'modelo', 'api_key', 'system_prompt')
        }),
        ('Integrações (APIs Externas)', {
            'fields': ('token_telecontrol',),
            'description': 'Chaves de acesso para sistemas externos (ex: Telecontrol).'
        }),
    )

    actions = ['testar_prompt']

    @admin.action(description="🔌 Despertar IA (Teste Real)")
    def testar_prompt(self, request, queryset):
        for config in queryset:
            print(f"\n--- Iniciando teste para: {config.nome} ---")
            print(f"Provedor: {config.provedor} | Modelo: {config.modelo}")
            if not config.api_key:
                print("❌ Parou: API Key está vazia.")
                self.message_user(request, "Sem chave, sem magia. Preencha a API Key.", level=messages.ERROR)
                continue

            try:
                fala_ia = ""
                mensagem_teste = "Aja exatamente conforme a sua persona e me dê um 'Olá' absurdamente criativo em apenas uma frase."

                # --- OPENAI SDK ---
                if config.provedor == 'openai':
                    print("🚀 Disparando para a API OpenAI...")
                    client = openai.OpenAI(api_key=config.api_key)
                    response = client.chat.completions.create(
                        model=config.modelo,
                        messages=[
                            {"role": "system", "content": config.system_prompt},
                            {"role": "user", "content": mensagem_teste}
                        ]
                    )
                    fala_ia = response.choices[0].message.content

                # --- GEMINI SDK ---
                elif config.provedor == 'gemini':
                    print("⏳ Invocando o Gemini via SDK...")
                    client = genai.Client(api_key=config.api_key)
                    response = client.models.generate_content(
                        model=config.modelo, 
                        contents=mensagem_teste,
                        config=types.GenerateContentConfig(
                            system_instruction=config.system_prompt,
                        )
                    )
                    fala_ia = response.text

                # --- CLAUDE (ANTHROPIC) SDK ---
                elif config.provedor == 'claude':
                    print("🧠 Acordando o Claude...")
                    client = anthropic.Anthropic(api_key=config.api_key)
                    response = client.messages.create(
                        model=config.modelo,
                        max_tokens=1024,
                        system=config.system_prompt,
                        messages=[
                            {"role": "user", "content": mensagem_teste}
                        ]
                    )
                    fala_ia = response.content[0].text
                
                print(f"✅ SUCESSO! A IA respondeu: {fala_ia}")
                self.message_user(request, f"🚀 {config.modelo} Acordou: '{fala_ia}'", level=messages.SUCCESS)

            except Exception as e:
                print(f"💥 EXCEÇÃO/CRASH: {str(e)}")
                self.message_user(request, f"Erro na Matrix ({config.provedor}): {str(e)}", level=messages.ERROR)