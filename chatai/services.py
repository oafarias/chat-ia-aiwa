# chatai/services.py
from .models import ConfiguracaoIA
from google import genai
from google.genai import types
import asyncio
from channels.db import database_sync_to_async
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
            # Limpa o CPF (deixa só números) para garantir que o filtro funcione
            cpf_limpo = ''.join(filter(str.isdigit, str(cpf_cliente)))
            mensagens = Mensagem.objects.filter(sala__cpf__contains=cpf_limpo).order_by('timestamp')
        else:
            mensagens = Mensagem.objects.filter(sala_id=sala_id).order_by('timestamp')
            
        historico = []
        for msg in mensagens:
            texto = msg.texto.strip()
            if not texto: continue
            role = "model" if msg.remetente_atendente else "user"
            historico.append(types.Content(role=role, parts=[types.Part.from_text(text=texto)]))
        return historico
    except Exception as e:
        print(f"DEBUG: Erro ao buscar historico CPF: {e}", flush=True)
        return []

async def perguntar_a_ia_stream(sala_id):
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
    
    if not mensagens_list:
        teve_anterior = len(historico) > 0
        
        # PROMPT DE RECEPÇÃO E BLINDAGEM (Oculto do Cliente)
        prompt_secreto = (
            f"INSTRUÇÃO DO SISTEMA: Você é o assistente virtual oficial da AIWA. "
            f"Um cliente acabou de abrir o chat. "
            f"O número do protocolo DESTA sessão que se inicia agora é: {sala_atual.protocolo}. "
            
            f"\n\nTAREFA 1 (Blindagem): O cliente informou que se chama '{sala_atual.cliente_nome}'. "
            f"Avalie silenciosamente se este nome é um palavrão, ofensa, ou um trocadilho "
            f"de mau gosto em português (ex: Tomas Turbando, Jacinto Pinto, etc). "
            f"Se for um nome 'troll' ou inapropriado, ignore-o e trate o cliente educadamente "
            f"apenas por 'Senhor(a)'. Se for um nome normal e válido, chame-o pelo nome."
            
            f"\n\nTAREFA 2 (Atendimento): Escreva a SUA PRIMEIRA MENSAGEM para o cliente agora. "
        )

        if teve_anterior:
            prompt_secreto += (
                "Notei que este cliente JÁ TEM HISTÓRICO conosco (leia as mensagens anteriores acima). "
                "Faça uma saudação de boas-vindas de retorno contextualizada, informe o novo protocolo "
                "e pergunte de forma empática se ele quer dar continuidade ao caso anterior ou "
                "se precisa de ajuda com algo novo."
            )
        else:
            prompt_secreto += (
                "Este é um CLIENTE NOVO. Dê as boas-vindas à AIWA, informe o número "
                "do protocolo dele e pergunte como você pode ajudá-lo hoje."
            )

        # Injetamos o prompt na lista que vai pro Gemini
        historico.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt_secreto)]))

    client = genai.Client(api_key=config.api_key)
    
    try:
        response = await client.aio.models.generate_content_stream(
            model="gemini-2.5-flash", # Ou a versão que está funcionando na sua API
            contents=historico,
            config=types.GenerateContentConfig(
                system_instruction=config.system_prompt,
                temperature=0.7,
            )
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text
                
    except Exception as e:
        print(f"--- ERRO CRÍTICO GEMINI --- \n{str(e)}", flush=True)
        yield "Estou com uma pequena instabilidade técnica, mas já estou voltando! 🛠️"