from django.shortcuts import render, redirect, get_object_or_404
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
            
        # Cria a sala APENAS (o Model já cuida de colocar na Fila Principal e gerar o protocolo)
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