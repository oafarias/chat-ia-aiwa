// Configura o Marked
marked.setOptions({ breaks: true });

// ==========================================
// 1. VALIDAÇÃO DO FORMULÁRIO DE ENTRADA (CPF)
// ==========================================
// Este bloco roda na tela inicial, onde o usuário digita o nome e CPF.
document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    const cpfInput = document.getElementById('cpf');

    function validarCPF(cpf) {
        cpf = cpf.replace(/[^\d]+/g, ''); 
        if (cpf === '' || cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;
        
        let soma = 0;
        for (let i = 1; i <= 9; i++) soma += parseInt(cpf.substring(i - 1, i)) * (11 - i);
        let resto = (soma * 10) % 11;
        if ((resto === 10) || (resto === 11)) resto = 0;
        if (resto !== parseInt(cpf.substring(9, 10))) return false;
        
        soma = 0;
        for (let i = 1; i <= 10; i++) soma += parseInt(cpf.substring(i - 1, i)) * (12 - i);
        resto = (soma * 10) % 11;
        if ((resto === 10) || (resto === 11)) resto = 0;
        if (resto !== parseInt(cpf.substring(10, 11))) return false;
        
        return true;
    }

    if (form && cpfInput) {
        // Máscara: impede digitar letras
        cpfInput.addEventListener('input', function(e) {
            let v = this.value.replace(/\D/g, ''); // Remove tudo o que não é dígito
            
            // Limita a 11 números no máximo
            if (v.length > 11) v = v.substring(0, 11);

            // Aplica a pontuação dinamicamente
            v = v.replace(/(\d{3})(\d)/, '$1.$2');       // Coloca o primeiro ponto
            v = v.replace(/(\d{3})(\d)/, '$1.$2');       // Coloca o segundo ponto
            v = v.replace(/(\d{3})(\d{1,2})$/, '$1-$2'); // Coloca o traço

            this.value = v; 
            this.style.borderColor = '#ddd'; // Reseta a cor caso estivesse vermelha do erro
        });

        // Validação no Envio
        form.addEventListener('submit', function(e) {
            if (!validarCPF(cpfInput.value)) {
                e.preventDefault(); 
                alert('⚠️ O CPF informado é inválido. Por favor, verifique os números e tente novamente.');
                cpfInput.style.borderColor = 'red'; 
                cpfInput.focus(); 
            }
        });
    }
});

// ==========================================
// 2. LÓGICA DO WEBSOCKET E CHAT
// ==========================================
// Este bloco roda na tela do chat, após a sala ser criada.
document.addEventListener("DOMContentLoaded", () => {
    // Pega as variáveis injetadas pelo Django com segurança
    const config = window.chatConfig || {};
    const salaId = config.salaId;
    const username = config.username;
    const avatarUrl = config.avatarUrl;

    // Se não tiver salaId, não tenta conectar (evita erros na home)
    if (!salaId || config.erroEncerrado === "true") return;

    // Processa histórico markdown inicial
    document.querySelectorAll('.markdown-content').forEach(el => {
        el.innerHTML = marked.parse(el.textContent);
    });
    const chatWindow = document.querySelector('#chat-window');
    if (chatWindow) chatWindow.scrollTop = chatWindow.scrollHeight;

    // Configuração de Áudio
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playChatSound() {
        try {
            const osc = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            osc.connect(gainNode);
            gainNode.connect(audioCtx.destination);
            osc.type = "sine";
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            gainNode.gain.setValueAtTime(0.05, audioCtx.currentTime);
            osc.start();
            gainNode.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + 0.1);
            osc.stop(audioCtx.currentTime + 0.1);
        } catch(e) {}
    }

    // Inicializa o WebSocket
    const protocolo = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const chatSocket = new WebSocket(
        protocolo + window.location.host + '/ws/chat/' + salaId + '/?tipo=consumidor'
    );

    chatSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        const chatWindow = document.querySelector('#chat-window');

        if (data.action === 'typing_start') {
            const typingContainer = document.querySelector('#typing-container');
            if (typingContainer) typingContainer.style.display = 'flex';
            chatWindow.scrollTop = chatWindow.scrollHeight;
            return;
        }

        if (data.action === 'stream_chunk') {
            const typingContainer = document.querySelector('#typing-container');
            if (typingContainer) typingContainer.style.display = 'none';

            let streamRow = document.querySelector('.stream-row');
            if (!streamRow) {
                streamRow = document.createElement('div');
                streamRow.className = 'msg-row msg-row-atendente stream-row';
                streamRow.dataset.rawText = ""; 
                streamRow.innerHTML = `
                    <img src="${avatarUrl}" class="msg-avatar">
                    <div class="msg-group msg-group-atendente">
                        <div class="msg msg-atendente msg-stream"></div>
                        <div class="msg-sender">${data.username}</div>
                    </div>
                `;
                chatWindow.appendChild(streamRow);
            }
            
            let streamDiv = streamRow.querySelector('.msg-stream');
            streamRow.dataset.rawText += data.message;
            streamDiv.innerHTML = marked.parse(streamRow.dataset.rawText);
            chatWindow.scrollTop = chatWindow.scrollHeight;
            return; 
        }

        if (data.action === 'stream_end') {
            const streamRow = document.querySelector('.stream-row');
            if (streamRow) {
                streamRow.classList.remove('stream-row');
                const streamDiv = streamRow.querySelector('.msg-stream');
                if (streamDiv) streamDiv.classList.remove('msg-stream');
            }
            return;
        }

        if (data.action === 'chat_ended') {
            alert("Este chat foi encerrado.");
            window.location.href = '/';
            return;
        }

        // Mensagens normais
        const msgRow = document.createElement('div');
        msgRow.className = (data.username === username) ? 'msg-row msg-row-cliente' : 'msg-row msg-row-atendente';
        
        let innerHTML = '';
        if (data.username !== username) {
            innerHTML += `<img src="${avatarUrl}" class="msg-avatar">`;
        }
        
        // Verificamos se quem enviou a mensagem é o próprio cliente logado
        const isMe = (data.username === username);
        
        // Definimos o nome: se for ele, aparece "Você". Se não, aparece o nome original (IA/Atendente)
        const senderLabel = isMe ? "Você" : data.username;

        innerHTML += `
            <div class="msg-group ${isMe ? 'msg-group-cliente' : 'msg-group-atendente'}">
                <div class="msg ${isMe ? 'msg-cliente' : 'msg-atendente'}">
                    ${marked.parse(data.message)}
                </div>
                <div class="msg-sender" ${isMe ? 'style="text-align: right; opacity: 0.7;"' : ''}>${senderLabel}</div>
            </div>
        `;
        
        msgRow.innerHTML = innerHTML;
        chatWindow.appendChild(msgRow);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        if (!isMe) playChatSound();
    };

    // Funções de Interação
    function enviarMensagem() {
        const input = document.querySelector('#input-mensagem');
        if (!input) return;
        const mensagem = input.value.trim();

        if (mensagem !== "" && chatSocket.readyState === WebSocket.OPEN) {
            chatSocket.send(JSON.stringify({ 'message': mensagem }));
            input.value = '';
        }
    }

    const btnEnviar = document.querySelector('#btn-enviar');
    const inputMensagem = document.querySelector('#input-mensagem');

    if (btnEnviar) btnEnviar.onclick = enviarMensagem;
    if (inputMensagem) {
        inputMensagem.onkeyup = (e) => { if (e.key === 'Enter') enviarMensagem(); };
    }

    const btnFinalizar = document.querySelector('#btn-finalizar-chat');
    if (btnFinalizar) {
        btnFinalizar.onclick = () => {
            if (confirm("Deseja encerrar o atendimento?")) {
                chatSocket.send(JSON.stringify({'action': 'close_chat'}));
                window.location.href = '/';
            }
        };
    }
});