// Configura o Marked
marked.setOptions({ breaks: true });

document.addEventListener("DOMContentLoaded", () => {
    // Processa histórico markdown
    document.querySelectorAll('.markdown-content').forEach(el => {
        el.innerHTML = marked.parse(el.textContent);
    });
    const chatWindow = document.querySelector('#chat-window');
    if (chatWindow) chatWindow.scrollTop = chatWindow.scrollHeight;

    // Configuração de áudio
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

    // Pega as variáveis injetadas pelo Django no HTML
    const salaId = window.chatConfig.salaId;
    const username = window.chatConfig.username;
    const avatarUrl = window.chatConfig.avatarUrl;

    if (salaId && !window.chatConfig.erroEncerrado) {
        const chatSocket = new WebSocket(
            (window.location.protocol === 'https:' ? 'wss://' : 'ws://') 
            + window.location.host + '/ws/chat/' + salaId + '/?tipo=consumidor'
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
                const msgRow = document.createElement('div');
                msgRow.className = 'msg-row msg-row-atendente';
                msgRow.innerHTML = `
                    <img src="${avatarUrl}" class="msg-avatar">
                    <div class="msg-group msg-group-atendente">
                        <div class="msg msg-atendente" style="background: #ffdada; color: #cc0000; font-weight: bold;">
                            Este chat foi finalizado pelo atendente ou a conexão caiu.
                        </div>
                        <div class="msg-sender">Sistema</div>
                    </div>
                `;
                chatWindow.appendChild(msgRow);
                chatWindow.scrollTop = chatWindow.scrollHeight;
                chatSocket.close();
                setTimeout(() => { window.location.href = '/'; }, 3000);
                return;
            }

            const msgRow = document.createElement('div');
            
            if (data.username === username) {
                msgRow.className = 'msg-row msg-row-cliente';
                msgRow.innerHTML = `
                    <div class="msg-group msg-group-cliente">
                        <div class="msg msg-cliente"></div>
                    </div>
                `;
                msgRow.querySelector('.msg').innerHTML = marked.parse(data.message);
            } else {
                msgRow.className = 'msg-row msg-row-atendente';
                msgRow.innerHTML = `
                    <img src="${avatarUrl}" class="msg-avatar">
                    <div class="msg-group msg-group-atendente">
                        <div class="msg msg-atendente"></div>
                        <div class="msg-sender">${data.username}</div>
                    </div>
                `;
                msgRow.querySelector('.msg').innerHTML = marked.parse(data.message);
            }
            
            chatWindow.appendChild(msgRow);
            chatWindow.scrollTop = chatWindow.scrollHeight;

            if (data.username !== username) {
                playChatSound();
            }
        };

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

        if (btnEnviar && inputMensagem) {
            btnEnviar.onclick = enviarMensagem;

            const btnFinalizar = document.querySelector('#btn-finalizar-chat');
            if (btnFinalizar) {
                btnFinalizar.onclick = function() {
                    if (confirm("Tem certeza que deseja finalizar este atendimento?")) {
                        chatSocket.send(JSON.stringify({'action': 'close_chat'}));
                        window.location.href = '/';
                    }
                };
            }
            inputMensagem.onkeyup = function(e) {
                if (e.key === 'Enter') { enviarMensagem(); }
            };
        }
    }
});