import openai
import anthropic
import requests
import json
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django import forms
from django.utils.safestring import mark_safe
from .models import ConfiguracaoIA, ApiExterna, BaseConhecimento
from google import genai
from google.genai import types

# ==============================================================================
# WIDGET CUSTOMIZADO: Markdown com Toggle (Leitura / Edição)
# ==============================================================================
class MarkdownToggleWidget(forms.Textarea):
    class Media:
        css = {
            'all': ('https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.css',)
        }
        js = (
            'https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.js',
            'https://cdn.jsdelivr.net/npm/marked/marked.min.js',
        )

    def render(self, name, value, attrs=None, renderer=None):
        html_textarea = super().render(name, value, attrs, renderer)
        if value is None:
            value = ""
        
        safe_value = json.dumps(value)

        custom_html = f"""
        <div class="md-widget-container" id="container_{name}" style="max-width: 850px; margin-bottom: 10px;">
            <!-- Barra de Ferramentas / Status -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; background: rgba(0,0,0,0.02);">
                <span style="font-size: 12px; font-weight: bold; opacity: 0.7;">👁️ MODO DE LEITURA</span>
                <button type="button" id="btn_edit_{name}" class="button" style="background-color: #417690; color: white; border: none; padding: 6px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; transition: 0.2s;">
                    ✏️ Habilitar Edição
                </button>
            </div>
            
            <!-- Modo Visualização (Markdown Renderizado e Limpo) -->
            <div id="preview_{name}" style="border: 1px solid #ccc; padding: 15px 20px; border-radius: 4px; min-height: 60px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; word-wrap: break-word;">
            </div>
            
            <!-- Modo Edição (Editor EasyMDE Escondido) -->
            <div id="editor_wrapper_{name}" style="display: none;">
                {html_textarea}
            </div>
        </div>

        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                const btn = document.getElementById("btn_edit_{name}");
                const preview = document.getElementById("preview_{name}");
                const editorWrapper = document.getElementById("editor_wrapper_{name}");
                const textarea = document.getElementById("id_{name}");
                const modeLabel = btn.previousElementSibling;
                
                // ADICIONADO 'lista_os' E 'lista_protocolos' AQUI! 👇
                const knownVars = ['nome', 'protocolo', 'lista_os', 'lista_protocolos'];
                
                // Função mágica para destacar as variáveis
                function formatVariables(rawText) {{
                    if (!rawText) return "";
                    // Expressão regular para achar tudo que está entre {{ e }}
                    return rawText.replace(/\{{([a-zA-Z0-9_]+)\}}/g, function(match, varName) {{
                        if (knownVars.includes(varName)) {{
                            // Variável Conhecida: Verde
                            return `<code style="color: #0f5132; background-color: #d1e7dd; border: 1px solid #badbcc; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.9em; font-weight: bold;">` + match + `</code>`;
                        }} else {{
                            // Variável Desconhecida/Erro: Vermelho
                            return `<code style="color: #842029; background-color: #f8d7da; border: 1px solid #f5c2c7; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.9em; font-weight: bold;" title="⚠️ Variável não reconhecida">` + match + `</code>`;
                        }}
                    }});
                }}

                // Atualiza a pré-visualização aplicando as cores primeiro, e depois o Markdown
                function renderPreview(text) {{
                    const processedText = formatVariables(text);
                    if (typeof marked !== 'undefined') {{
                        preview.innerHTML = marked.parse(processedText);
                    }} else {{
                        preview.innerHTML = processedText;
                    }}
                }}

                // Inicia renderizando o valor salvo no banco
                renderPreview({safe_value});

                let mdeInstance = null;

                // Lógica de clique do botão
                btn.addEventListener("click", function(e) {{
                    e.preventDefault();
                    if (editorWrapper.style.display === "none") {{
                        // LIGA O MODO EDIÇÃO
                        editorWrapper.style.display = "block";
                        preview.style.display = "none";
                        btn.innerHTML = "💾 Travar Edição";
                        btn.style.backgroundColor = "#28a745"; // Verde Sucesso
                        modeLabel.innerText = "✍️ MODO DE EDIÇÃO (MARKDOWN)";
                        modeLabel.style.color = "#28a745";
                        modeLabel.style.opacity = "1";
                        
                        if (!mdeInstance && typeof EasyMDE !== 'undefined') {{
                            mdeInstance = new EasyMDE({{ 
                                element: textarea,
                                spellChecker: false,
                                status: false,
                                toolbar: ["bold", "italic", "heading", "|", "quote", "unordered-list", "ordered-list", "|", "preview", "guide"]
                            }});
                        }}
                    }} else {{
                        // VOLTA PARA O MODO LEITURA
                        editorWrapper.style.display = "none";
                        preview.style.display = "block";
                        btn.innerHTML = "✏️ Habilitar Edição";
                        btn.style.backgroundColor = "#417690"; // Azul Django
                        modeLabel.innerText = "👁️ MODO DE LEITURA";
                        modeLabel.style.color = "inherit";
                        modeLabel.style.opacity = "0.7";
                        
                        const newValue = mdeInstance ? mdeInstance.value() : textarea.value;
                        renderPreview(newValue);
                    }}
                }});
            }});
        </script>
        """
        return mark_safe(custom_html)


# ==============================================================================
# FORMULÁRIO CUSTOMIZADO PARA APLICAR O WIDGET
# ==============================================================================
class ConfiguracaoIAForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoIA
        fields = '__all__'
        widgets = {
            'prompt_saudacao_nova': MarkdownToggleWidget(),
            'prompt_saudacao_retorno': MarkdownToggleWidget(),
            'prompt_andamento': MarkdownToggleWidget(),
            'prompt_raciocinio': MarkdownToggleWidget(),
            'prompt_contexto_os': MarkdownToggleWidget(), 
            'prompt_contexto_protocolo': MarkdownToggleWidget(), # Widget para a nova caixa de Protocolo
            'system_prompt': MarkdownToggleWidget(),
        }


# ==============================================================================
# CLASSES DE ADMINISTRAÇÃO ORIGINAIS
# ==============================================================================
@admin.register(ConfiguracaoIA)
class ConfiguracaoIAAdmin(admin.ModelAdmin):
    form = ConfiguracaoIAForm
    
    list_display = ('nome', 'provedor', 'modelo', 'is_active')
    list_filter = ('provedor', 'is_active')
    
    fieldsets = (
        ('Informações Principais', {
            'fields': ('nome', 'is_active')
        }),
        ('Motor da IA', {
            'fields': ('provedor', 'modelo', 'api_key', 'system_prompt')
        }),
        ('Prompts de Contexto (Dinâmicos)', {
            'fields': ('prompt_saudacao_nova', 'prompt_saudacao_retorno', 'prompt_andamento', 'prompt_raciocinio'),
            'description': 'Textos injetados dinamicamente dependendo do status do chat. Não remova as variáveis entre chaves {}.'
        }),
        ('Integrações (APIs Externas)', {
            'fields': (
                'api_os_vinculada', 'prompt_contexto_os',
                'api_protocolo_vinculada', 'prompt_contexto_protocolo' # Adicionado os campos de Protocolo
            ),
            'description': 'Ligue as APIs externas configuradas para fornecer contexto real à esta IA e dite como ela deve interpretar esses dados.'
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


@admin.register(ApiExterna)
class ApiExternaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'identificador', 'metodo', 'is_active')
    list_filter = ('is_active', 'metodo')
    search_fields = ('nome', 'identificador', 'url_base')
    actions = ['testar_api']

    @admin.action(description="🧪 Testar API Externa")
    def testar_api(self, request, queryset):
        if request.method == 'POST' and 'parametro_teste' in request.POST:
            parametro = request.POST.get('parametro_teste').strip()
            
            for api in queryset:
                if '{' not in api.url_base:
                    self.message_user(
                        request, 
                        f"⚠️ AVISO ({api.nome}): A URL base não possui variáveis como {{cpf}}! O parâmetro será ignorado.", 
                        level=messages.WARNING
                    )
                
                url = api.url_base.replace('{cpf}', parametro).replace('{id}', parametro)
                
                headers_dict = {}
                if isinstance(api.headers, dict):
                    headers_dict = api.headers
                elif isinstance(api.headers, str) and api.headers.strip():
                    try:
                        headers_dict = json.loads(api.headers.replace("'", '"'))
                    except Exception:
                        pass
                
                try:
                    print(f"🚀 Testando API Externa: {api.nome}")
                    print(f"URL Montada: {url}")
                    print(f"Headers Enviados: {list(headers_dict.keys())}")
                    
                    resp = requests.request(api.metodo, url, headers=headers_dict, timeout=10)
                    
                    if resp.status_code == 200:
                        if not resp.text.strip():
                            self.message_user(request, f"⚠️ AVISO ({api.nome}): Status 200 OK, mas o corpo da resposta está vazio.", level=messages.WARNING)
                        else:
                            try:
                                dados = resp.json()
                                res_str = json.dumps(dados, ensure_ascii=False)[:150]
                                self.message_user(request, f"✅ SUCESSO ({api.nome}) | URL: {url} | JSON: {res_str}...", level=messages.SUCCESS)
                            except ValueError:
                                self.message_user(request, f"❌ ERRO DE PARSE ({api.nome}) | URL: {url} | API não retornou JSON. Início: {resp.text[:100]}", level=messages.ERROR)
                    else:
                        self.message_user(request, f"⚠️ AVISO ({api.nome}): Status {resp.status_code} | Resposta: {resp.text[:150]}", level=messages.WARNING)
                except Exception as e:
                    self.message_user(request, f"❌ ERRO ({api.nome}): {str(e)}", level=messages.ERROR)
            
            return HttpResponseRedirect(request.get_full_path())

        csrf_token = get_token(request)
        
        selected_inputs = "".join(
            f'<input type="hidden" name="_selected_action" value="{obj.pk}">' 
            for obj in queryset
        )
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Testar API Externa</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8f9fa; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                .card {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 450px; width: 100%; text-align: center; border-top: 5px solid #417690; box-sizing: border-box; }}
                input[type="text"] {{ width: 100%; padding: 12px; margin: 15px 0; border: 1px solid #ccc; border-radius: 4px; font-size: 16px; outline: none; box-sizing: border-box; }}
                input[type="text"]:focus {{ border-color: #417690; }}
                button {{ background: #417690; color: white; border: none; padding: 12px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold; transition: 0.2s; box-sizing: border-box; }}
                button:hover {{ background: #2c5d77; }}
                .cancel {{ display: block; margin-top: 15px; color: #d9534f; text-decoration: none; font-size: 14px; }}
                .cancel:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2 style="margin-top: 0; color: #333;">Testar API</h2>
                <p style="color: #666; line-height: 1.5;">Digite o valor para substituir a variável na URL<br><em>(Ex: um CPF válido para testar a Telecontrol)</em></p>
                <form method="POST" action="">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
                    <input type="hidden" name="action" value="testar_api">
                    {selected_inputs}
                    <input type="text" name="parametro_teste" placeholder="Ex: 12345678901" required autofocus>
                    <button type="submit">Disparar Teste 🚀</button>
                </form>
                <a href="javascript:history.back()" class="cancel">Cancelar e Voltar</a>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html)

@admin.register(BaseConhecimento)
class BaseConhecimentoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'ativo', 'atualizado_em')
    list_filter = ('ativo', 'criado_em')
    search_fields = ('titulo', 'conteudo')
    readonly_fields = ('id', 'criado_em', 'atualizado_em')