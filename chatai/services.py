from .models import ConfiguracaoIA
from google import genai
from google.genai import types
import asyncio
from asgiref.sync import sync_to_async


async def perguntar_a_ia_stream(mensagem_usuario):
    """
    Busca a configuração ativa e envia a mensagem para a IA correspondente.
    """
    config = await sync_to_async(lambda: ConfiguracaoIA.objects.filter(is_active=True).first())()
    
    if not config or config.provedor != 'gemini':
        yield "Desculpe, o bot de inteligência artificial está indisponível. 💤"
        return

    # Usamos o client.aio para trabalhar perfeitamente com os WebSockets do Channels
    client = genai.Client(api_key=config.api_key)
    
    response = await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash", 
        contents=mensagem_usuario,
        config=types.GenerateContentConfig(
            system_instruction=config.system_prompt,
        )
    )
    
    async for chunk in response:
        if chunk.text:
            yield chunk.text