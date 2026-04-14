from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from chatconsumidor.models import SalaDeChat, Mensagem, Fila # Import Fila
from .models import Atendente

@login_required(login_url='/admin/login/')
def painel(request, sala_id=None):
    perfil = get_object_or_404(Atendente, user=request.user)
    
    # 1. Salas que estão na fila deste atendente
    salas_ativas = SalaDeChat.objects.filter(atendente=perfil, status='ativo')
    
    # 2. Busca todas as filas (para permitir que o atendente transfira o chat)
    todas_as_filas = Fila.objects.all()
    
    sala_selecionada = None
    mensagens = []

    if sala_id:
        sala_selecionada = get_object_or_404(SalaDeChat, id=sala_id, atendente=perfil)
        
        # 3. LÓGICA DE CONTEXTO (CPF): 
        # Busca mensagens de TODAS as conversas anteriores deste CPF
        if sala_selecionada.cpf:
            mensagens = Mensagem.objects.filter(
                sala__cpf=sala_selecionada.cpf
            ).order_by('timestamp')
        else:
            mensagens = sala_selecionada.mensagens.all()

    return render(request, 'chatatendente/painel.html', {
        'salas': salas_ativas,
        'sala_selecionada': sala_selecionada,
        'mensagens': mensagens,
        'filas': todas_as_filas, # Enviando filas para o atendente poder mover o chat
        'perfil': perfil
    })

@login_required(login_url='/admin/login/')
def encerrar_chat(request, sala_id):
    if request.method == "POST":
        perfil = get_object_or_404(Atendente, user=request.user)
        sala = get_object_or_404(SalaDeChat, id=sala_id, atendente=perfil)
        
        if sala.status != 'encerrado':
            sala.status = 'encerrado'
            sala.encerrado_por = 'atendente' # Registra quem encerrou
            sala.save()
                
    return redirect('painel')