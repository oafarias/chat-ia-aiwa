from django.shortcuts import render, get_object_or_404, redirect
from chatconsumidor.models import SalaDeChat, Mensagem, Atendente

def painel(request, sala_id=None):
    perfil = get_object_or_404(Atendente, user=request.user)
    salas_ativas = SalaDeChat.objects.filter(atendente=perfil, status='ativo')
    
    sala_selecionada = None
    mensagens = []

    if sala_id:
        sala_selecionada = get_object_or_404(SalaDeChat, id=sala_id, atendente=perfil)
        mensagens = sala_selecionada.mensagens.all()

        if request.method == "POST":
            texto = request.POST.get('mensagem')
            if texto:
                Mensagem.objects.create(sala=sala_selecionada, texto=texto, remetente_atendente=perfil)
                return redirect('painel_sala', sala_id=sala_id)

    return render(request, 'chatatendente/painel.html', {
        'salas': salas_ativas,
        'sala_selecionada': sala_selecionada,
        'mensagens': mensagens
    })