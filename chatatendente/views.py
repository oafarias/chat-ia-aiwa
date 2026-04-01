from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from chatconsumidor.models import SalaDeChat, Mensagem
from .models import Atendente

@login_required(login_url='/admin/login/')
def painel(request, sala_id=None):
    perfil = get_object_or_404(Atendente, user=request.user)
    salas_ativas = SalaDeChat.objects.filter(atendente=perfil, status='ativo')
    
    sala_selecionada = None
    mensagens = []

    if sala_id:
        sala_selecionada = get_object_or_404(SalaDeChat, id=sala_id, atendente=perfil)
        mensagens = sala_selecionada.mensagens.all()

    return render(request, 'chatatendente/painel.html', {
        'salas': salas_ativas,
        'sala_selecionada': sala_selecionada,
        'mensagens': mensagens
    })

@login_required(login_url='/admin/login/')
def encerrar_chat(request, sala_id):
    if request.method == "POST":
        perfil = get_object_or_404(Atendente, user=request.user)
        sala = get_object_or_404(SalaDeChat, id=sala_id, atendente=perfil)
        
        if sala.status != 'encerrado':
            # 1. Muda o status da sala
            sala.status = 'encerrado'
            sala.save()
                
    # Redireciona de volta para o painel limpo
    return redirect('painel')