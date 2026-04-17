import requests
from channels.db import database_sync_to_async

@database_sync_to_async
def buscar_os_telecontrol(cpf, token):
    """
    Consulta a API da Telecontrol para buscar Ordens de Serviço vinculadas ao CPF.
    Agora utiliza o token (access-application-key) dinamicamente a partir do banco de dados.
    """
    if not token:
        print("Aviso: Token da Telecontrol não configurado no painel Admin.")
        return []
        
    url = f"https://api2.telecontrol.com.br/os/ordem/cpf/{cpf}"
    
    # Injeção do token vindo do Models/Admin no Header da requisição
    headers = {
        "access-env": "PRODUCTION",
        "access-application-key": token
    }
    
    try:
        # Adicionado um timeout por segurança para não travar o chat se a API externa cair
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            dados = resp.json()
            # Retorna a lista de OSs ou uma lista vazia se a chave "os" não existir
            return dados.get("os", [])
        else:
            print(f"Aviso API Telecontrol: Status {resp.status_code} - {resp.text}")
            return []
            
    except Exception as e:
        print(f"Erro de conexão com a API Telecontrol: {e}")
        return []