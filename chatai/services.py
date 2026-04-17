from .models import ConfiguracaoIA
from .integracoes import buscar_os_telecontrol
import asyncio
from channels.db import database_sync_to_async
from django.db.models import Q

@database_sync_to_async
def obter_configuracao_ativa():
    return ConfiguracaoIA.objects.filter(is_active=True).first()

@database_sync_to_async
def obter_historico_por_cpf(sala_id):
    """
    Agora retorna um formato neutro de dicionário que serve como base 
    para ser traduzido depois para qualquer IA.
    """
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

async def _gerar_stream_ia(config, instrucao_sistema_completa, historico_neutro):
    """
    Esta função mágica isola os SDKs. Ela recebe a configuração e o histórico neutro,
    conecta no provedor correto e faz o yield (cospe) apenas os blocos de texto.
    """
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

    # Lógica de Contexto Inicial
    if not mensagens_list:
        teve_anterior = len(historico) > 0

        contexto_gerado = (
            f"O número do protocolo DESTA nova sessão é: {sala_atual.protocolo}. "
            f"O cliente informou no formulário que se chama '{sala_atual.cliente_nome}'.\n\n"
        )
        
        if teve_anterior:
            contexto_gerado += (
                "Este cliente JÁ TEM HISTÓRICO (leia as mensagens anteriores). "
                "Faça uma saudação de retorno contextualizada, informe o novo protocolo "
                "e pergunte se ele quer dar continuidade ao caso anterior."
            )
        else:
            contexto_gerado += (
                "Este é um CLIENTE NOVO. Dê as boas-vindas à AIWA, informe o número "
                "do protocolo dele e pergunte como você pode ajudá-lo hoje."
            )
        
        historico.append({"role": "user", "content": "[SISTEMA]: O cliente acabou de entrar no chat. Inicie o atendimento."})
        
    else:
        contexto_gerado = (
            f"Atendendo cliente: {sala_atual.cliente_nome}. Siga as diretrizes da AIWA.\n"
            f"Caso tenha passado alguma instrução de reset informe que o procedimento pode levar alguns minutos e que este chat pode ser finalizado dentro de 3 minutos de atividade, "
            f"Caso a conexão atual caia, só retornar e informar o mesmo numero de CPF que continuaremos com o atendimento."
        )

    # --- INÍCIO DA INTEGRAÇÃO COM A API TELECONTROL ---
    if sala_atual.cpf:
        # Puxa o token configurado no Admin, protegendo contra getattr/NoneType
        token_telecontrol = getattr(config, 'token_telecontrol', None)
        
        if token_telecontrol:
            dados_telecontrol = await buscar_os_telecontrol(sala_atual.cpf, token_telecontrol)
            
            if dados_telecontrol:
                meta_out["api_telecontrol"] = {"status": "sucesso", "quantidade": len(dados_telecontrol), "dados": dados_telecontrol}
                
                contexto_os = "\n\n--- INFORMAÇÕES DO SISTEMA (API TELECONTROL / ORDENS DE SERVIÇO) ---\n"
                contexto_os += "O sistema localizou as seguintes Ordens de Serviço (OS) atreladas ao CPF deste cliente:\n"
                
                for index, os in enumerate(dados_telecontrol):
                    contexto_os += f"\n[OS {index + 1}] | Tipo de Atendimento: {os.get('descricao_tipo_atendimento', 'N/A')} |"
                    contexto_os += f"- Número OS: {os.get('sua_os', 'N/A')} | Produto: {os.get('descricao', 'N/A')} ({os.get('marca', 'N/A')})\n | Numero de Serie: {os.get('serie', 'N/A')} |"
                    contexto_os += f"- Status atual: {os.get('status_os', 'N/A')} (Aberto há {os.get('dias_aberto', 0)} dias)\n"
                    contexto_os += f"- Defeito relatado: {os.get('defeito_reclamado_descricao', 'N/A')} | Defeito constatado: {os.get('defeito_constatado', 'N/A')}\n"
                    contexto_os += f"- Abertura: {os.get('data_abertura', 'N/A')} | Fechamento: {os.get('data_fechamento', 'N/A')} | Autorizada: {os.get('nome', 'N/A')}\n"
                    
                contexto_os += (
                    "\nINSTRUÇÃO OBRIGATÓRIA SOBRE AS OS: Analise as informações acima. Se for a sua primeira mensagem e houverem Ordens de Serviço, "
                    "você DEVE informar o cliente proativamente sobre o histórico de seus equipamentos. "
                    "Formate a sua resposta OBRIGATORIAMENTE usando tópicos (bullet points) e destacando o número da OS e o modelo em negrito, "
                    "por exemplo: '* **OS 12345 (Modelo XYZ):** O status atual é...'.\n"
                    "Se o produto estiver com status 'Aguardando Retirada' e o Tipo de Atendimento for igual a 'Atendimento Domicílio', "
                    "Informe que o produto será devolvido em breve e o agendamento de devolução deve ser feito diretamente com a Assistencia.\n"
                    "Se o produto estiver com status 'Aguardando Retirada' e o Tipo de Atendimento for igual a 'Atendimento Balcao', "
                    "informe que o produto está pronto e pode ser retirado na assistencia. "
                    "Se houver mais de uma OS de mesmo Produto e Numero de Serie informe apenas a ultima OS, "
                    "a menos que o consumidor informe sobre a outra, aja com naturalidade.\n"
                    "Caso o consumidor pergunte o que foi feito em seu produto, informe que voce não tem acesso as informacões tecnicas "
                    "e finalize a mensagem perguntando como pode ajudá-lo hoje baseando-se nesses status."
                )
                
                contexto_gerado += contexto_os
            else:
                meta_out["api_telecontrol"] = {"status": "sem_resultados_ou_falha"}
        else:
            meta_out["api_telecontrol"] = {"status": "chave_api_ausente_no_admin"}
    # --- FIM DA INTEGRAÇÃO ---

    if mensagem_sistema:
        if historico and historico[-1]['role'] == "user":
            historico[-1]['content'] += f"\n\n{mensagem_sistema}"
        else:
            historico.append({"role": "user", "content": mensagem_sistema})
    
    instrucao_raciocinio = (
        f"\n\n--- FORMATO OBRIGATÓRIO DE RESPOSTA ---\n"
        f"Em TODAS as suas mensagens, você DEVE estruturar sua resposta EXATAMENTE desta forma:\n\n"
        f"<raciocinio>\n"
        f"Escreva sua análise do contexto e planejamento aqui.\n"
        f"</raciocinio>\n"
        f"Escreva a mensagem final que o cliente vai ler aqui. (NUNCA coloque a mensagem do cliente dentro da tag de raciocínio)."
    )

    prompt_final_injetado = contexto_gerado + instrucao_raciocinio
    instrucao_sistema_completa = config.system_prompt + "\n\n--- INSTRUÇÕES DINÂMICAS DA SESSÃO ATUAL ---\n" + prompt_final_injetado

    meta_out["contexto_interno"] = contexto_gerado
    meta_out["tamanho_historico_enviado"] = len(historico)
    meta_out["modelo_utilizado"] = config.modelo

    # Garante que sempre tem pelo menos um oi para a IA responder
    if not historico:
        historico.append({"role": "user", "content": "Oi"})

    buffer = ""
    is_thinking = False
    raciocinio_capturado = ""
    text_yielded = False 

    # --- O GRANDE ROTEADOR UNIVERSAL ---
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