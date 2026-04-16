from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import SalaDeChat

def index(request):
    erro = None
    if request.method == "POST":
        nome_bruto = request.POST.get('nome', '').strip()
        cpf = request.POST.get('cpf', '').strip()
        
        # Validação simples
        if not nome_bruto or not cpf:
            erro = "Por favor, preencha o seu nome e CPF para iniciar o atendimento."
            return render(request, 'chatconsumidor/index.html', {'erro': erro})
            
        # 1. BLOQUEIO DE CHATS SIMULTÂNEOS:
        # Verifica se o cliente já tem um chat que não esteja 'encerrado'
        chat_ativo = SalaDeChat.objects.filter(cpf=cpf).exclude(status='encerrado').first()
        
        if chat_ativo:
            # Envia um aviso gentil (se o seu HTML usar mensagens do Django)
            messages.info(request, "Você já possui um atendimento em andamento. Retomando a conexão...")
            return redirect('sala_chat', sala_id=chat_ativo.id)

        # 2. Cria a sala APENAS se ele não tiver chat ativo
        nova_sala = SalaDeChat.objects.create(
            cliente_nome=nome_bruto, # Salvamos como o cliente digitou
            cpf=cpf,
            atendente=None,
            status='aguardando'
        )

        # Não criamos mais nenhuma Mensagem aqui! Deixamos a sala vazia para a IA agir.
        return redirect('sala_chat', sala_id=nova_sala.id)

    return render(request, 'chatconsumidor/index.html', {'erro': erro})

def sala_chat(request, sala_id):
    sala = get_object_or_404(SalaDeChat, id=sala_id)
    if sala.status == 'encerrado':
        return render(request, 'chatconsumidor/index.html', {'erro_chat_encerrado': True})
    return render(request, 'chatconsumidor/index.html', {'sala': sala})