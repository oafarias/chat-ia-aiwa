import requests
from django.contrib import admin
from django.contrib import messages
from .models import ConfiguracaoIA
from google import genai
from google.genai import types

@admin.register(ConfiguracaoIA)
class ConfiguracaoIAAdmin(admin.ModelAdmin):
    list_display = ('nome', 'provedor', 'is_active')
    list_filter = ('provedor', 'is_active')
    actions = ['testar_prompt']

    @admin.action(description="🔌 Despertar IA (Teste Real)")
    def testar_prompt(self, request, queryset):
        for config in queryset:
            print(f"\n--- Iniciando teste para: {config.nome} ---")
            print(f"Provedor: {config.provedor}")
            if not config.api_key:
                print("❌ Parou: API Key está vazia.")
                self.message_user(request, "Sem chave, sem magia. Preencha a API Key.", level=messages.ERROR)
                continue

            # Bloco de disparo para OpenAI (Mantido intacto)
            if config.provedor == 'openai':
                headers = {
                    "Authorization": f"Bearer {config.api_key}", 
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": config.system_prompt},
                        {"role": "user", "content": "Aja exatamente conforme a sua persona e me dê um 'Olá' absurdamente criativo em apenas uma frase."}
                    ]
                }
                
                try:
                    print("🚀 Disparando para a API OpenAI...")
                    resp = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                    print(f"📡 Retorno HTTP: {resp.status_code}")
                    
                    if resp.status_code == 200:
                        fala_ia = resp.json()['choices'][0]['message']['content']
                        print(f"✅ SUCESSO! A IA respondeu: {fala_ia}")
                        self.message_user(request, f"🧠 A IA Acordou: '{fala_ia}'", level=messages.SUCCESS)
                    else:
                        print(f"⚠️ ERRO DA API: {resp.text}")
                        self.message_user(request, f"Erro na Matrix (API): {resp.text}", level=messages.ERROR)
                except Exception as e:
                    print(f"💥 EXCEÇÃO/CRASH: {str(e)}")
                    self.message_user(request, f"Curto-circuito: {str(e)}", level=messages.ERROR)
            
            # Novo Bloco de disparo para Gemini (SDK Oficial)
            elif config.provedor == 'gemini':
                print("⏳ Invocando o Gemini via SDK...")
                try:
                    # Inicializa o client injetando a chave salva no banco
                    client = genai.Client(api_key=config.api_key)
                    
                    print("🚀 Disparando...")
                    # Passando o system prompt de forma limpa nas configurações
                    response = client.models.generate_content(
                        model="gemini-2.5-flash", 
                        contents="Aja exatamente conforme a sua persona e me dê um 'Olá' absurdamente criativo em apenas uma frase.",
                        config=types.GenerateContentConfig(
                            system_instruction=config.system_prompt,
                        )
                    )
                    
                    fala_ia = response.text
                    print(f"✅ SUCESSO! A IA respondeu: {fala_ia}")
                    self.message_user(request, f"🧠 A IA Acordou: '{fala_ia}'", level=messages.SUCCESS)
                    
                except Exception as e:
                    print(f"💥 EXCEÇÃO: {str(e)}")
                    self.message_user(request, f"Erro na Matrix (Gemini SDK): {str(e)}", level=messages.ERROR)