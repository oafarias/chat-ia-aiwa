import requests
from channels.db import database_sync_to_async

@database_sync_to_async
def buscar_os_telecontrol(cpf, api_config):
    """
    Consulta a API da Telecontrol para buscar Ordens de Serviço vinculadas ao CPF.
    """
    if not api_config or not api_config.is_active:
        print("Aviso: Configuração da API Telecontrol de OS não encontrada ou inativa no Admin.")
        return []
        
    url = api_config.url_base.replace("{cpf}", str(cpf))
    headers = api_config.headers if api_config.headers else {}
    
    try:
        resp = requests.request(api_config.metodo, url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            dados = resp.json()
            
            # 1. Extração segura da lista (tolerância a várias chaves)
            if isinstance(dados, dict):
                lista_bruta = dados.get("os", dados.get("dados", dados.get("data", [])))
            elif isinstance(dados, list):
                lista_bruta = dados
            else:
                lista_bruta = []
                
            # 2. Filtro Anti-Duplicatas (Proteção contra respostas sujas da API externa)
            os_vistas = set()
            lista_unica = []
            for item in lista_bruta:
                if isinstance(item, dict):
                    # Tenta pegar o identificador único da OS (sua_os ou os)
                    id_os = str(item.get("sua_os") or item.get("os") or "").strip()
                    if id_os:
                        if id_os in os_vistas:
                            continue # Ignora completamente se for uma OS duplicada
                        os_vistas.add(id_os)
                lista_unica.append(item)
                
            return lista_unica
        else:
            print(f"Aviso API OS: Status {resp.status_code} - {resp.text}")
            return []
            
    except Exception as e:
        print(f"Erro de conexão com a API de OS: {e}")
        return []


@database_sync_to_async
def buscar_protocolos_telecontrol(cpf, api_config):
    """
    Consulta a API para buscar o histórico de Protocolos vinculados ao CPF.
    """
    if not api_config or not api_config.is_active:
        return []
        
    url = api_config.url_base.replace("{cpf}", str(cpf))
    headers = api_config.headers if api_config.headers else {}
    
    try:
        resp = requests.request(api_config.metodo, url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            dados = resp.json()
            
            # 1. Extração segura da lista
            if isinstance(dados, dict):
                lista_bruta = dados.get("protocolos", dados.get("dados", dados.get("data", [])))
            elif isinstance(dados, list):
                lista_bruta = dados
            else:
                lista_bruta = []
                
            # 2. Filtro Anti-Duplicatas para Protocolos
            prot_vistos = set()
            lista_unica = []
            for item in lista_bruta:
                if isinstance(item, dict):
                    # Tenta pegar o identificador do protocolo
                    id_prot = str(item.get("protocolo") or item.get("numero") or item.get("id") or "").strip()
                    if id_prot:
                        if id_prot in prot_vistos:
                            continue # Ignora se já o viu antes
                        prot_vistos.add(id_prot)
                lista_unica.append(item)
                
            return lista_unica
        else:
            print(f"Aviso API Protocolos: Status {resp.status_code} - {resp.text}")
            return []
            
    except Exception as e:
        print(f"Erro de conexão com a API de Protocolos: {e}")
        return []