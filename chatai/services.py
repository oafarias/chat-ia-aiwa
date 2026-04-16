from .models import ConfiguracaoIA
from google import genai
from google.genai import types
import asyncio
from channels.db import database_sync_to_async
from django.db.models import Q
import sys

@database_sync_to_async
def obter_configuracao_ativa():
    return ConfiguracaoIA.objects.filter(is_active=True).first()

@database_sync_to_async
def obter_historico_por_cpf(sala_id):
    from chatconsumidor.models import Mensagem, SalaDeChat
    try:
        sala_atual = SalaDeChat.objects.get(id=sala_id)
        cpf_cliente = sala_atual.cpf
        
        if cpf_cliente:
            # FIX: Busca segura. Pega mensagens da sala ATUAL ou de qualquer sala com o mesmo CPF
            mensagens = Mensagem.objects.filter(
                Q(sala_id=sala_id) | Q(sala__cpf=cpf_cliente)
            ).order_by('timestamp')
        else:
            mensagens = Mensagem.objects.filter(sala_id=sala_id).order_by('timestamp')
            
        historico = []
        for msg in mensagens:
            texto = msg.texto.strip()
            if not texto: continue
            role = "model" if msg.remetente_atendente else "user"
            
            # FIX: GEMINI EXIGE ALTERNÂNCIA (Agrupa mensagens consecutivas do mesmo remetente)
            if historico and historico[-1].role == role:
                historico[-1].parts[0].text += f"\n\n{texto}"
            else:
                historico.append(types.Content(role=role, parts=[types.Part.from_text(text=texto)]))
                
        return historico
    except Exception as e:
        print(f"DEBUG: Erro ao buscar historico CPF: {e}", flush=True)
        return []

async def perguntar_a_ia_stream(sala_id, meta_out=None):
    if meta_out is None:
        meta_out={}

    config = await obter_configuracao_ativa()
    if not config:
        yield "Configuração da IA não encontrada no Admin. 💤"
        return

    from chatconsumidor.models import SalaDeChat, Mensagem
    sala_atual = await database_sync_to_async(SalaDeChat.objects.get)(id=sala_id)
    
    # Busca a memória global (todas as salas daquele CPF)
    historico = await obter_historico_por_cpf(sala_id)
    
    # Verifica se a sala ATUAL está vazia (para dar o gatilho inicial)
    mensagens_list = await database_sync_to_async(lambda: list(Mensagem.objects.filter(sala_id=sala_id)))()
    
    contexto_gerado = ""

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
        
        historico.append(types.Content(role="user", parts=[types.Part.from_text(text="[SISTEMA]: O cliente acabou de entrar no chat. Inicie o atendimento.")]))
        
    else:
        contexto_gerado = (
            f"Atendendo cliente: {sala_atual.cliente_nome}. Siga as diretrizes da AIWA."
        )
    
    # FIX: Instruções ultrarígidas de formatação para evitar a "IA Muda"
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

    client = genai.Client(api_key=config.api_key)
    
    try:
        # Failsafe final para evitar erro 400 se o array ficar vazio
        if not historico:
            historico.append(types.Content(role="user", parts=[types.Part.from_text(text="Oi")]))

        response = await client.aio.models.generate_content_stream(
            model="gemini-3-flash-preview",
            contents=historico,
            config=types.GenerateContentConfig(
                system_instruction=instrucao_sistema_completa,
                temperature=0.6,
            )
        )

        buffer = ""
        is_thinking = False
        raciocinio_capturado = ""
        text_yielded = False  # Rastreador se enviamos algo pro chat

        async for chunk in response:
            if not chunk.text: continue
            buffer += chunk.text

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
                        break # Espera o próximo chunk da API
                else:
                    end_idx = buffer.find("</raciocinio>")
                    if end_idx != -1:
                        # Acabou de pensar! Guarda o raciocinio oculto.
                        raciocinio_capturado += buffer[:end_idx]
                        buffer = buffer[end_idx + len("</raciocinio>"):]
                        is_thinking = False
                    else:
                        # Continua acumulando o pensamento oculto
                        if len(buffer) > 15:
                            raciocinio_capturado += buffer[:-15]
                            buffer = buffer[-15:]
                        break # Espera o próximo chunk da API

        # Ao fim do stream, limpa qualquer coisa que tenha sobrado no buffer
        if buffer:
            if is_thinking:
                raciocinio_capturado += buffer
            else:
                yield buffer
                text_yielded = True

        # Salva o monólogo interno na nossa variável de banco de dados
        if raciocinio_capturado:
            meta_out["linha_de_raciocinio"] = raciocinio_capturado.strip()
            
        # FIX: Failsafe. Se a IA colocar todo o texto dentro de <raciocinio> sem querer
        if not text_yielded:
            yield "Desculpe, estava analisando seus dados e acabei me perdendo. Como posso te ajudar agora?"

        # --- CAPTURANDO TOKENS ---
        try:
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                meta_out["tokens"] = {
                    "prompt": response.usage_metadata.prompt_token_count,
                    "resposta": response.usage_metadata.candidates_token_count,
                    "total": response.usage_metadata.total_token_count
                }
        except Exception as token_err:
            meta_out["tokens_info"] = "Não foi possível extrair tokens nesta resposta."

    except Exception as e:
        print(f"--- ERRO CRÍTICO GEMINI --- \n{str(e)}", flush=True)
        yield "Estou com uma pequena instabilidade técnica, mas já estou voltando! 🛠️"