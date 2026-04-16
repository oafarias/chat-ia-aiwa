import httpx
import re
from django.conf import settings

async def buscar_os_telecontrol(cpf):
    """
    Realiza uma busca assíncrona na API da Telecontrol usando o CPF do cliente.
    Retorna uma lista de dicionários com as OSs encontradas ou uma lista vazia.
    """
    if not cpf:
        return []

    # Remove qualquer pontuação (pontos e traços) que possa ter vindo do banco
    cpf_limpo = re.sub(r'\D', '', str(cpf))
    
    url = f"https://api2.telecontrol.com.br/os/ordem/cpf/{cpf_limpo}"
    
    headers = {
        "access-env": "PRODUCTION",
        "access-application-key": settings.TELECONTROL_API_KEY
    }

    try:
        # Usamos httpx.AsyncClient para não bloquear a thread principal do Channels.
        # Definimos um timeout de 5 segundos. Se a API deles cair, o chat não cai.
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                dados = response.json()
                # Retorna a lista que está dentro da chave 'os', ou [] se não existir
                return dados.get("os", [])
            else:
                print(f"DEBUG: API Telecontrol retornou erro HTTP {response.status_code}", flush=True)
                return []
                
    except httpx.RequestError as e:
        # Pega timeouts, problemas de DNS ou recusas de conexão
        print(f"DEBUG: Falha de conexão com a API Telecontrol: {e}", flush=True)
        return []
    except Exception as e:
        # Pega erros de Parsing (JSON quebrado, etc)
        print(f"DEBUG: Erro inesperado ao processar API Telecontrol: {e}", flush=True)
        return []