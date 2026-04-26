import uuid
from django.db import models
from .vector_db import vector_db

class ConfiguracaoIA(models.Model):
    PROVEDORES = [
        ('openai', 'OpenAI (ChatGPT)'),
        ('gemini', 'Google Gemini'),
        ('claude', 'Anthropic (Claude)'),
    ]

    nome = models.CharField(max_length=50, help_text="Ex: Bot de Vendas Agressivo")
    provedor = models.CharField(max_length=20, choices=PROVEDORES, default='openai')
    modelo = models.CharField(
        max_length=100, 
        default='gpt-4o-mini', 
        help_text="Digite o nome exato da API. Dicas: 'gpt-4o', 'gpt-4o-mini', 'gemini-2.5-flash', 'gemini-1.5-pro', 'claude-3-5-sonnet-20241022'."
    )
    api_key = models.CharField(max_length=255)
    system_prompt = models.TextField(help_text="A personalidade e regras da IA", default="Você é um assistente prestativo.")
    is_active = models.BooleanField(default=False, verbose_name="Ativo?")

    # --- APIs EXTERNAS VINCULADAS ---
    api_os_vinculada = models.ForeignKey(
        'ApiExterna',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='configuracoes_os', # Obrigatório ter related_name para não dar conflito
        verbose_name="API de Consulta de OS",
        help_text="Selecione qual API Externa esta IA deve usar para consultar Ordens de Serviço pelo CPF."
    )
    
    api_protocolo_vinculada = models.ForeignKey(
        'ApiExterna',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='configuracoes_protocolo', # Obrigatório ter related_name
        verbose_name="API de Consulta de Protocolos",
        help_text="Selecione qual API Externa esta IA deve usar para consultar os Protocolos do cliente."
    )

    # --- CAMPOS DE PROMPT DA SESSÃO ---
    prompt_saudacao_nova = models.TextField(
        verbose_name="Saudação (Novo Cliente)",
        default="O número do protocolo DESTA nova sessão é: {protocolo}. O cliente informou no formulário que se chama '{nome}'.\n\nEste é um CLIENTE NOVO. Dê as boas-vindas à AIWA, informe o número do protocolo dele e pergunte como você pode ajudá-lo hoje.",
        help_text="Use {protocolo} e {nome} para injetar os dados dinâmicos."
    )
    prompt_saudacao_retorno = models.TextField(
        verbose_name="Saudação (Cliente Retornando)",
        default="O número do protocolo DESTA nova sessão é: {protocolo}. O cliente informou no formulário que se chama '{nome}'.\n\nEste cliente JÁ TEM HISTÓRICO (leia as mensagens anteriores). Faça uma saudação de retorno contextualizada, informe o novo protocolo e pergunte se ele quer dar continuidade ao caso anterior.",
        help_text="Use {protocolo} e {nome} para injetar os dados dinâmicos."
    )
    prompt_andamento = models.TextField(
        verbose_name="Instrução (Chat em Andamento)",
        default="Atendendo cliente: {nome}. Siga as diretrizes da AIWA.\nCaso tenha passado alguma instrução de reset informe que o procedimento pode levar alguns minutos e que este chat pode ser finalizado dentro de 3 minutos de atividade. Caso a conexão atual caia, só retornar e informar o mesmo numero de CPF que continuaremos com o atendimento.",
        help_text="Use {nome} para injetar o nome do cliente."
    )
    prompt_raciocinio = models.TextField(
        verbose_name="Regra de Raciocínio (Obrigatório)",
        default="\n\n--- FORMATO OBRIGATÓRIO DE RESPOSTA ---\nEm TODAS as suas mensagens, você DEVE estruturar sua resposta EXATAMENTE desta forma:\n\n<raciocinio>\nEscreva sua análise do contexto e planejamento aqui.\n</raciocinio>\nEscreva a mensagem final que o cliente vai ler aqui. (NUNCA coloque a mensagem do cliente dentro da tag de raciocínio).",
        help_text="Instrução fixa que obriga a IA a pensar antes de responder."
    )
    
    prompt_contexto_os = models.TextField(
        verbose_name="Instrução de Ordens de Serviço",
        default="\n\n--- INFORMAÇÕES DO SISTEMA (API TELECONTROL / ORDENS DE SERVIÇO) ---\nO sistema localizou as seguintes Ordens de Serviço (OS) da marca AIWA atreladas ao CPF deste cliente:\n{lista_os}\n\nINSTRUÇÃO OBRIGATÓRIA SOBRE AS OS: Analise as informações acima. Se for a sua primeira mensagem e houverem Ordens de Serviço, você DEVE informar o cliente proativamente sobre o histórico de seus equipamentos. Formate a sua resposta OBRIGATORIAMENTE usando tópicos (bullet points) e destacando o número da OS e o modelo em negrito, por exemplo: '* **OS 12345 (Modelo XYZ):** O status atual é...'.\nSe o produto estiver com status 'Aguardando Retirada' e o Tipo de Atendimento for igual a 'Atendimento Domicílio', Informe que o produto será devolvido em breve e o agendamento de devolução deve ser feito diretamente com a Assistencia.\nSe o produto estiver com status 'Aguardando Retirada' e o Tipo de Atendimento for igual a 'Atendimento Balcao', informe que o produto está pronto e pode ser retirado na assistencia. Se houver mais de uma OS de mesmo Produto e Numero de Serie informe apenas a ultima OS, a menos que o consumidor informe sobre a outra, aja com naturalidade.\nCaso o consumidor pergunte o que foi feito em seu produto, informe que voce não tem acesso as informacões tecnicas e finalize a mensagem perguntando como pode ajudá-lo hoje baseando-se nesses status.",
        help_text="Instrução injetada apenas quando o cliente possui OSs válidas. Use a variável {lista_os}."
    )

    prompt_contexto_protocolo = models.TextField(
        verbose_name="Instrução de Protocolos (Telecontrol)",
        default="\n\n--- INFORMAÇÕES DO SISTEMA (PROTOCOLOS ANTERIORES) ---\nO sistema localizou os seguintes protocolos atrelados a este CPF:\n{lista_protocolos}\n\nINSTRUÇÃO: Caso o cliente questione sobre atendimentos ou protocolos anteriores, utilize as informações acima para atualizar o status do caso dele de forma resumida e prestativa.",
        help_text="Instrução injetada apenas quando o cliente possui protocolos válidos. Use a variável {lista_protocolos}."
    )

    def save(self, *args, **kwargs):
        if self.is_active:
            ConfiguracaoIA.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        status = "🟢 ATIVO" if self.is_active else "🔴 Inativo"
        return f"{self.nome} ({self.get_provedor_display()} | {self.modelo}) - {status}"

    class Meta:
        verbose_name = "Configuração de IA"
        verbose_name_plural = "Configurações de IA"


class ApiExterna(models.Model):
    METODOS = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
    ]

    nome = models.CharField(max_length=100, help_text="Ex: Consulta de OS Telecontrol")
    identificador = models.SlugField(
        unique=True, 
        help_text="ID usado no código para buscar esta API. Ex: 'telecontrol_os'"
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo?")
    url_base = models.CharField(
        max_length=255, 
        help_text="URL completa. Use chaves para variáveis, ex: https://api.com/os/{cpf}"
    )
    metodo = models.CharField(max_length=10, choices=METODOS, default='GET')
    headers = models.JSONField(
        default=dict, 
        blank=True, 
        help_text='Formato JSON. Ex: {"access-env": "PRODUCTION", "access-application-key": "SEU_TOKEN"}'
    )

    def __str__(self):
        status = "🟢 ATIVA" if self.is_active else "🔴 Inativa"
        return f"{self.nome} ({self.metodo}) - {status}"

    class Meta:
        verbose_name = "API Externa"
        verbose_name_plural = "APIs Externas"

class BaseConhecimento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=200, help_text="Ex: Regras de Garantia de TVs, Saudação Inicial, etc.")
    conteudo = models.TextField(help_text="O fragmento de texto com o conhecimento que a IA deve aprender.")
    ativo = models.BooleanField(default=True, help_text="Se desmarcado, a IA não usará este texto.")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Base de Conhecimento"
        verbose_name_plural = "Bases de Conhecimento"
        ordering = ['-atualizado_em']

    def __str__(self):
        return f"{self.titulo} ({'Ativo' if self.ativo else 'Inativo'})"

    # --- NOVO: Interceptando o momento de Salvar e Deletar ---

    def save(self, *args, **kwargs):
        # 1. Primeiro salvamos normalmente no banco SQL do Django
        super().save(*args, **kwargs)
        
        # 2. Depois, espelhamos a mudança no Banco Vetorial
        if self.ativo:
            # Se estiver ativo, mandamos pra OpenAI gerar o vetor e salvamos no ChromaDB
            vector_db.adicionar_ou_atualizar_documento(self.id, self.titulo, self.conteudo)
        else:
            # Se o admin desmarcou a caixinha "ativo", nós apagamos do ChromaDB pra IA não usar mais
            vector_db.deletar_documento(self.id)

    def delete(self, *args, **kwargs):
        # Se o admin excluir o registro no Django, excluímos do vetor também
        vector_db.deletar_documento(self.id)
        super().delete(*args, **kwargs)