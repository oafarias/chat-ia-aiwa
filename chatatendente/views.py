from django.shortcuts import render

def painel(request):
    return render(request, 'chatatendente/painel.html')
