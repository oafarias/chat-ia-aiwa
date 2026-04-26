import chromadb
import os
from django.conf import settings
from openai import OpenAI
from dotenv import load_dotenv

# Força o carregamento do .env para garantir que a chave esteja disponível
load_dotenv()

class VectorDBManager:
    def __init__(self):
        # Inicializa o cliente da OpenAI AQUI DENTRO (seguro)
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Configura o ChromaDB para salvar os dados numa pasta local chamada "chroma_data"
        persist_directory = os.path.join(settings.BASE_DIR, "chroma_data")
        
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Cria ou pega a "tabela" (coleção) onde guardaremos os textos da AIWA
        self.collection = self.client.get_or_create_collection(
            name="aiwa_base_conhecimento",
            metadata={"hnsw:space": "cosine"}
        )

    def _gerar_embedding(self, texto):
        """Usa a OpenAI para transformar o texto em um vetor de números."""
        response = self.openai_client.embeddings.create(
            input=texto,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    def adicionar_ou_atualizar_documento(self, doc_id, titulo, conteudo):
        """Gera o embedding e salva no ChromaDB."""
        texto_completo = f"Título: {titulo}\nConteúdo: {conteudo}"
        vetor = self._gerar_embedding(texto_completo)
        
        self.collection.upsert(
            ids=[str(doc_id)],
            embeddings=[vetor],
            documents=[texto_completo],
            metadatas=[{"titulo": titulo}]
        )

    def deletar_documento(self, doc_id):
        """Remove o documento do banco vetorial."""
        try:
            self.collection.delete(ids=[str(doc_id)])
        except Exception as e:
            print(f"Erro ao deletar documento do ChromaDB: {e}")

    def buscar_contexto_relevante(self, pergunta_cliente, n_resultados=2):
        """Busca os fragmentos de texto mais relevantes para a pergunta do cliente."""
        try:
            # 1. Transforma a pergunta do cliente em coordenadas (vetor)
            vetor_pergunta = self._gerar_embedding(pergunta_cliente)
            
            # 2. Faz a busca matemática no ChromaDB
            resultados = self.collection.query(
                query_embeddings=[vetor_pergunta],
                n_results=n_resultados
            )
            
            # 3. Pega os textos encontrados (se houver)
            documentos = resultados.get('documents', [[]])[0]
            
            if not documentos:
                return ""
                
            # 4. Junta tudo num texto só para mandar pra IA
            texto_contexto = "\n\n".join(documentos)
            return f"\n\n[INSTRUÇÃO IMPORTANTE: BASE DE CONHECIMENTO]\nResponda o cliente utilizando APENAS as regras abaixo caso sejam relevantes para a pergunta. Não mencione que você consultou a base.\n{texto_contexto}\n[FIM DO CONTEXTO]"
            
        except Exception as e:
            print(f"Erro na busca vetorial: {e}")
            return ""

# Instância global para usarmos em outras partes do projeto
vector_db = VectorDBManager()