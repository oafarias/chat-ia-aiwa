# **🤖 AIWA Chat IA**

Sistema de atendimento inteligente que integra o poder da Inteligência Artificial (Google Gemini) com a eficiência do suporte humano em tempo real.

## **🚀 Funcionalidades**

* **Chat Consumidor:** Interface fluida para interação do usuário final.  
* **Integração com IA:** Respostas automáticas e inteligentes utilizando o modelo Gemini Pro.  
* **Painel do Atendente:** Gerenciamento de filas e salas de chat para suporte humano.  
* **Real-time:** Comunicação via WebSockets utilizando Django Channels.  
* **Docker Ready:** Ambiente totalmente containerizado para facilitar o deploy.

## **🛠️ Tecnologias**

* **Backend:** Python / Django  
* **Assincronismo:** Django Channels / Redis  
* **IA:** Google Generative AI (Gemini Pro)  
* **Frontend:** HTML5, CSS3, JavaScript  
* **DevOps:** Docker / Docker Compose

## **📦 Estrutura do Projeto**

* chatai/: Serviços e integrações com a API de IA.  
* chatatendente/: Lógica e templates do painel de suporte.  
* chatconsumidor/: Interface e sockets para o cliente final.  
* setup/: Configurações principais do projeto (ASGI/WSGI).

## **🔧 Como Executar**

### **Via Docker (Recomendado)**

1. Certifique-se de ter o Docker e Docker Compose instalados.  
2. Crie um arquivo .env na raiz com suas credenciais (veja seção abaixo).  
3. Execute o comando:  
   docker-compose up \--build

### **Localmente**

1. Instale as dependências:  
   pip install \-r requirements.txt

2. Realize as migrações:  
   python manage.py migrate

3. Inicie o servidor:  
   python manage.py runserver

## **🔑 Variáveis de Ambiente**

Crie um arquivo .env para configurar as chaves necessárias:

| Variável | Descrição |
| :---- | :---- |
| GOOGLE\_API\_KEY | Sua chave da API do Google Gemini |
| REDIS\_URL | URL do Redis para o layer do Channels |
| DEBUG | Define se o Django roda em modo debug |

Desenvolvido e inspirado para a **AIWA**.