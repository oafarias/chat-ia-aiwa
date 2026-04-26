from .models import ConfiguracaoIA, ApiExterna
from .integracoes import buscar_os_telecontrol, buscar_protocolos_telecontrol
from .vector_db import vector_db
import asyncio
import json
import time
from channels.db import database_sync_to_async
from django.db.models import Q
from asgiref.sync import sync_to_async

@database_sync_to_async
def obter_configuracao_ativa():
    return ConfiguracaoIA.objects.select_related('api_os_vinculada', 'api_protocolo_vinculada').filter(is_active=True).first()

@database_sync_to_async
def obter_historico_por_cpf(sala_id):
    from chatconsumidor.models import Mensagem, SalaDeChat
    try:
        sala_atual = SalaDeChat.objects.get(id=sala_id)
        cpf_cliente = sala_atual.cpf
        
        if cpf_cliente:
            mensagens = Mensagem.objects.filter(
                Q(sala_id=sala_id) | Q(sala__cpf=cpf_cliente)
            ).order_by('timestamp')
        else:
            mensagens = Mensagem.objects.filter(sala_id=sala_id).order_by('timestamp')
            
        historico = []
        for msg in mensagens:
            texto = msg.texto.strip()
            if not texto: continue
            role = "assistant" if msg.remetente_atendente else "user"
            
            if historico and historico[-1]['role'] == role:
                historico[-1]['content'] += f"\n\n{texto}"
            else:
                historico.append({"role": role, "content": texto})
                
        return historico
    except Exception as e:
        print(f"DEBUG: Erro ao buscar historico CPF: {e}", flush=True)
        return []

# =========================================================
# ORQUESTRADOR MULTIAGENTE (SEMANTIC ROUTER)
# =========================================================
async def _decidir_ferramentas(config, ultima_pergunta):
    """
    Atua como um 'Supervisor'. Analisa a pergunta e decide quais bancos de dados consultar.
    """
    fallback_orquestrador = """Você é o Orquestrador de Ferramentas da AIWA.
Sua única função é ler a mensagem do usuário e decidir quais sistemas consultar.

Sistemas disponíveis:
- "base_conhecimento": Use para dúvidas sobre produtos, como fazer algo, regras de garantia, campanhas ou qualquer pergunta informativa.
- "ordens_servico": Use APENAS se o cliente perguntar sobre o status de um conserto, assistência técnica ou OS.
- "protocolos": Use APENAS se o cliente mencionar que já tem um protocolo anterior.

Retorne OBRIGATORIAMENTE um JSON válido com a lista de sistemas a consultar. Exemplo:
{"sistemas": ["base_conhecimento"]}
Se for apenas um cumprimento ("Oi", "Bom dia"), retorne: {"sistemas": []}."""

    prompt_base = getattr(config, 'prompt_orquestrador', fallback_orquestrador)
    prompt_completo = f"{prompt_base}\n\nMensagem do usuário: \"{ultima_pergunta}\""

    try:
        if config.provedor == 'gemini':
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=config.api_key)
            response = await client.aio.models.generate_content(
                model=config.modelo, 
                contents=prompt_completo,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            resultado = json.loads(response.text)
            return resultado.get("sistemas", [])
            
        elif config.provedor == 'openai':
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=config.api_key)
            response = await client.chat.completions.create(
                model=config.modelo,
                messages=[{"role": "user", "content": prompt_completo}],
                response_format={ "type": "json_object" },
                temperature=0.1
            )
            resultado = json.loads(response.choices[0].message.content)
            return resultado.get("sistemas", [])
            
        else:
            return ["base_conhecimento", "ordens_servico", "protocolos"]
            
    except Exception as e:
        print(f"Erro no Orquestrador: {e}", flush=True)
        return ["base_conhecimento", "ordens_servico", "protocolos"]

async def _mock_result(value=None):
    return value

async def _gerar_stream_ia(config, instrucao_sistema_completa, historico_neutro):
    try:
        if config.provedor == 'gemini':
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=config.api_key)
            
            historico_formatado = []
            for h in historico_neutro:
                role_g = "model" if h["role"] == "assistant" else "user"
                historico_formatado.append(types.Content(role=role_g, parts=[types.Part.from_text(text=h["content"])]))
                
            response = await client.aio.models.generate_content_stream(
                model=config.modelo,
                contents=historico_formatado,
                config=types.GenerateContentConfig(
                    system_instruction=instrucao_sistema_completa,
                    temperature=0.6,
                )
            )
            async for chunk in response:
                if chunk.text: yield chunk.text

        elif config.provedor == 'openai':
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=config.api_key)
            
            mensagens = [{"role": "system", "content": instrucao_sistema_completa}] + historico_neutro
            response = await client.chat.completions.create(
                model=config.modelo,
                messages=mensagens,
                temperature=0.6,
                stream=True
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        elif config.provedor == 'claude':
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=config.api_key)
            
            async with client.messages.stream(
                model=config.modelo,
                max_tokens=2048,
                temperature=0.6,
                system=instrucao_sistema_completa,
                messages=historico_neutro,
            ) as stream:
                async for text in stream.text_stream:
                    yield text

    except Exception as e:
        print(f"--- ERRO CRÍTICO {config.provedor.upper()} --- \n{str(e)}", flush=True)
        yield "Estou com uma pequena instabilidade técnica, mas já estou voltando! 🛠️"

async def perguntar_a_ia_stream(sala_id, meta_out=None, mensagem_sistema=None):
    if meta_out is None:
        meta_out={}

    config = await obter_configuracao_ativa()
    if not config:
        yield "Configuração da IA não encontrada no Admin. 💤"
        return

    from chatconsumidor.models import SalaDeChat, Mensagem
    sala_atual = await database_sync_to_async(SalaDeChat.objects.get)(id=sala_id)
    
    historico = await obter_historico_por_cpf(sala_id)
    mensagens_list = await database_sync_to_async(lambda: list(Mensagem.objects.filter(sala_id=sala_id)))()
    
    contexto_gerado = ""

    fallback_novo = "O número do protocolo DESTA nova sessão é: {protocolo}. O cliente informou no formulário que se chama '{nome}'.\n\nEste é um CLIENTE NOVO. Dê as boas-vindas à AIWA, informe o número do protocolo dele e pergunte como você pode ajudá-lo hoje."
    fallback_retorno = "O número do protocolo DESTA nova sessão é: {protocolo}. O cliente informou no formulário que se chama '{nome}'.\n\nEste cliente JÁ TEM HISTÓRICO (leia as mensagens anteriores). Faça uma saudação de retorno contextualizada, informe o novo protocolo e pergunte se ele quer dar continuidade ao caso anterior."
    fallback_andamento = "Atendendo cliente: {nome}. Siga as diretrizes da AIWA.\nCaso tenha passado alguma instrução de reset informe que o procedimento pode levar alguns minutos e que este chat pode ser finalizado dentro de 3 minutos de atividade. Caso a conexão atual caia, só retornar e informar o mesmo numero de CPF que continuaremos com o atendimento."
    
    if not mensagens_list:
        teve_anterior = len(historico) > 0
        
        if teve_anterior:
            template_retorno = getattr(config, 'prompt_saudacao_retorno', fallback_retorno)
            contexto_gerado = template_retorno.format(
                protocolo=sala_atual.protocolo,
                nome=sala_atual.cliente_nome
            )
        else:
            template_novo = getattr(config, 'prompt_saudacao_nova', fallback_novo)
            contexto_gerado = template_novo.format(
                protocolo=sala_atual.protocolo,
                nome=sala_atual.cliente_nome
            )
        
        historico.append({"role": "user", "content": "[SISTEMA]: O cliente acabou de entrar no chat. Inicie o atendimento."})
        
    else:
        template_andamento = getattr(config, 'prompt_andamento', fallback_andamento)
        contexto_gerado = template_andamento.format(
            nome=sala_atual.cliente_nome
        )

    # 1. Identifica a real mensagem do cliente
    ultima_pergunta = ""
    for msg in reversed(historico):
        if msg.get("role") == "user" and not msg.get("content", "").startswith("[SISTEMA]"):
            ultima_pergunta = msg.get("content", "")
            break

    # 2. Orquestrador decide o que fazer
    ferramentas_necessarias = ["base_conhecimento", "ordens_servico", "protocolos"]
    if ultima_pergunta:
        t0_orq = time.time()
        ferramentas_necessarias = await _decidir_ferramentas(config, ultima_pergunta)
        print(f"\n🧠 Orquestrador decidiu consultar: {ferramentas_necessarias} em {time.time() - t0_orq:.2f}s", flush=True)

    # 3. Prepara as Tarefas Paralelas (Subagentes)
    print("--- [EXECUÇÃO DE FERRAMENTAS EM PARALELO] ---", flush=True)
    t0_tools = time.time()
    tarefas = []

    # Tarefa 0: RAG (Base de Conhecimento)
    if "base_conhecimento" in ferramentas_necessarias and ultima_pergunta:
        tarefas.append(sync_to_async(vector_db.buscar_contexto_relevante)(ultima_pergunta))
    else:
        tarefas.append(_mock_result(""))

    # Tarefa 1: Ordens de Serviço (Telecontrol)
    api_os = config.api_os_vinculada
    if "ordens_servico" in ferramentas_necessarias and sala_atual.cpf and api_os and api_os.is_active:
        tarefas.append(buscar_os_telecontrol(sala_atual.cpf, api_os))
    else:
        tarefas.append(_mock_result(None))

    # Tarefa 2: Protocolos (Telecontrol)
    api_protocolo = config.api_protocolo_vinculada
    if "protocolos" in ferramentas_necessarias and sala_atual.cpf and api_protocolo and api_protocolo.is_active:
        tarefas.append(buscar_protocolos_telecontrol(sala_atual.cpf, api_protocolo))
    else:
        tarefas.append(_mock_result(None))

    # 4. Dispara todas juntas e aguarda os resultados
    resultados = await asyncio.gather(*tarefas)
    contexto_rag, dados_os_brutos, dados_protocolo = resultados
    print(f"⏱️ Ferramentas finalizadas em: {time.time() - t0_tools:.2f}s\n", flush=True)

    # 5. Injeta os resultados que voltaram preenchidos
    if contexto_rag:
        contexto_gerado += f"\n{contexto_rag}\n"

    if dados_os_brutos:
        dados_os_filtrados = [
            os_item for os_item in dados_os_brutos 
            if str(os_item.get('marca', '')).strip().upper() == 'AIWA'
        ]
        
        if dados_os_filtrados:
            meta_out["api_os"] = {"status": "sucesso", "quantidade": len(dados_os_filtrados)}
            
            lista_os_str = ""
            for index, os_item in enumerate(dados_os_filtrados):
                lista_os_str += f"\n[OS {index + 1}] | Tipo: {os_item.get('descricao_tipo_atendimento', 'N/A')} |"
                lista_os_str += f" Número: {os_item.get('sua_os', 'N/A')} | Produto: {os_item.get('descricao', 'N/A')} |"
                lista_os_str += f" Status: {os_item.get('status_os', 'N/A')} | Abertura: {os_item.get('data_abertura', 'N/A')}\n"
            
            fallback_os = "\n\n--- INFORMAÇÕES DO SISTEMA (API TELECONTROL / ORDENS DE SERVIÇO) ---\nO sistema localizou as seguintes Ordens de Serviço (OS) da marca AIWA atreladas ao CPF deste cliente:\n{lista_os}\n\nINSTRUÇÃO OBRIGATÓRIA SOBRE AS OS: Analise as informações acima. Se for a sua primeira mensagem e houverem Ordens de Serviço, você DEVE informar o cliente proativamente sobre o histórico de seus equipamentos. Formate a sua resposta OBRIGATORIAMENTE usando tópicos (bullet points) e destacando o número da OS e o modelo em negrito."
            template_os = getattr(config, 'prompt_contexto_os', fallback_os)
            contexto_gerado += template_os.format(lista_os=lista_os_str)
        else:
            meta_out["api_os"] = {"status": "sem_resultados_aiwa"}
    elif "ordens_servico" in ferramentas_necessarias and sala_atual.cpf:
        meta_out["api_os"] = {"status": "vazio"}

    if dados_protocolo:
        meta_out["api_protocolo"] = {"status": "sucesso", "quantidade": len(dados_protocolo)}
        
        lista_prot_str = json.dumps(dados_protocolo, ensure_ascii=False, indent=2)
        
        fallback_prot = "\n\n--- INFORMAÇÕES DO SISTEMA (PROTOCOLOS ANTERIORES) ---\nO sistema localizou os seguintes protocolos atrelados a este CPF:\n{lista_protocolos}\n\nINSTRUÇÃO: Caso o cliente questione sobre atendimentos ou protocolos anteriores, utilize as informações acima."
        template_prot = getattr(config, 'prompt_contexto_protocolo', fallback_prot)
        contexto_gerado += template_prot.format(lista_protocolos=lista_prot_str)
    elif "protocolos" in ferramentas_necessarias and sala_atual.cpf:
        meta_out["api_protocolo"] = {"status": "vazio"}

    # =========================================================

    if mensagem_sistema:
        if historico and historico[-1]['role'] == "user":
            historico[-1]['content'] += f"\n\n{mensagem_sistema}"
        else:
            historico.append({"role": "user", "content": mensagem_sistema})
            
    fallback_raciocinio = "\n\n--- FORMATO OBRIGATÓRIO DE RESPOSTA ---\nEm TODAS as suas mensagens, a sua primeiríssima palavra deve ser a tag <raciocinio>. NÃO ESCREVA NADA antes da tag.\n\n<raciocinio>\nEscreva sua análise do contexto e planejamento aqui. SE UTILIZAR A BASE DE CONHECIMENTO, liste explicitamente o 'Título' das regras que está usando.\n</raciocinio>\nEscreva a mensagem final que o cliente vai ler aqui. (NUNCA coloque a mensagem do cliente dentro da tag de raciocínio)."
    instrucao_raciocinio = getattr(config, 'prompt_raciocinio', fallback_raciocinio)

    prompt_final_injetado = contexto_gerado + instrucao_raciocinio
    instrucao_sistema_completa = config.system_prompt + "\n\n--- INSTRUÇÕES DINÂMICAS DA SESSÃO ATUAL ---\n" + prompt_final_injetado

    meta_out["contexto_interno"] = contexto_gerado
    meta_out["tamanho_historico_enviado"] = len(historico)
    meta_out["modelo_utilizado"] = config.modelo

    if not historico:
        historico.append({"role": "user", "content": "Oi"})

    buffer = ""
    is_thinking = False
    raciocinio_capturado = ""
    text_yielded = False 

    t0_llm = time.time()
    print(f"🚀 Iniciando Streaming do Agente Final...", flush=True)
    stream_generator = _gerar_stream_ia(config, instrucao_sistema_completa, historico)

    async for chunk_text in stream_generator:
        buffer += chunk_text

        while True:
            if not is_thinking:
                start_idx = buffer.find("<raciocinio>")
                if start_idx != -1:
                    texto_limpo = buffer[:start_idx]
                    if texto_limpo: 
                        yield texto_limpo
                        text_yielded = True

                    buffer = buffer[start_idx + len("<raciocinio>"):]
                    is_thinking = True
                else:
                    if len(buffer) > 15:
                        chunk_yield = buffer[:-15]
                        yield chunk_yield
                        text_yielded = True
                        buffer = buffer[-15:]
                    break 
            else:
                end_idx = buffer.find("</raciocinio>")
                if end_idx != -1:
                    raciocinio_capturado += buffer[:end_idx]
                    buffer = buffer[end_idx + len("</raciocinio>"):]
                    is_thinking = False
                else:
                    if len(buffer) > 15:
                        raciocinio_capturado += buffer[:-15]
                        buffer = buffer[-15:]
                    break 

    print(f"✅ Tempo total do Streaming: {time.time() - t0_llm:.2f}s\n", flush=True)

    if buffer:
        if is_thinking:
            raciocinio_capturado += buffer
        else:
            yield buffer
            text_yielded = True

    if raciocinio_capturado:
        meta_out["linha_de_raciocinio"] = raciocinio_capturado.strip()
        
    if not text_yielded:
        yield "Desculpe, estava analisando seus dados e acabei me perdendo. Como posso te ajudar agora?"