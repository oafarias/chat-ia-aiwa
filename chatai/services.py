from .models import ConfiguracaoIA
from google import genai
from google.genai import types
import asyncio
from channels.db import database_sync_to_async

@database_sync_to_async
def obter_configuracao_ativa():
    """Isola a chamada síncrona ao banco de dados"""
    return ConfiguracaoIA.objects.filter(is_active=True).first()

@database_sync_to_async
def obter_historico(sala_id):
    """Busca a conversa e traduz para o cérebro da IA"""
    from chatconsumidor.models import Mensagem # Import local para evitar erro circular
    
    mensagens = Mensagem.objects.filter(sala_id=sala_id).order_by('id')
    historico = []
    
    for msg in mensagens:
        if not msg.texto.strip():
            continue
        # Se tem remetente_atendente, foi a IA. Se não tem, foi o Cliente.
        role = "model" if msg.remetente_atendente else "user"
        historico.append(
            types.Content(role=role, parts=[types.Part.from_text(text=msg.texto)])
        )
        
    return historico

async def perguntar_a_ia_stream(sala_id):
    """Busca a configuração ativa e envia o histórico para a IA."""
    config = await obter_configuracao_ativa()
    
    if not config or config.provedor != 'gemini':
        yield "Desculpe, o bot de inteligência artificial está indisponível. 💤"
        return

    # A Mágica: Recuperamos toda a memória da conversa
    historico = await obter_historico(sala_id)

    client = genai.Client(api_key=config.api_key)
    
    response = await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash", 
        contents=historico, # <-- Passando o histórico ao invés de uma única string
        config=types.GenerateContentConfig(
            system_instruction=config.system_prompt,
        )
    )
    
    async for chunk in response:
        if chunk.text:
            yield chunk.text