from django.shortcuts import render, redirect, get_object_or_404
from .models import SalaDeChat, atribuir_atendente

def index(request):

    print(f"--- Nova requisição recebida: {request.method} ---")

    if request.method == "POST":
        nome = request.POST.get('nome')
        atendente_sorteado = atribuir_atendente()
        
        # ESTE PRINT PRECISA ESTAR EXATAMENTE AQUI (com 8 espaços de recuo)
        print(f"DEBUG: Sorteando atendente para {nome}. Resultado: {atendente_sorteado}")

        nova_sala = SalaDeChat.objects.create(
            cliente_nome=nome,
            atendente=atendente_sorteado,
            status='ativo' if atendente_sorteado else 'aguardando'
        )

        if atendente_sorteado:
            atendente_sorteado.chats_ativos += 1
            atendente_sorteado.save()

        return redirect('sala_chat', sala_id=nova_sala.id)

    return render(request, 'chatconsumidor/index.html')

def sala_chat(request, sala_id):
    sala = get_object_or_404(SalaDeChat, id=sala_id)
    return render(request, 'chatconsumidor/index.html', {'sala': sala})