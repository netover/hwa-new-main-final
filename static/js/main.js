document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Element Selectors ---
    const workstationsTotalEl = document.getElementById('workstations-total');
    const jobsAbendEl = document.getElementById('jobs-abend');
    const jobsSuccEl = document.getElementById('jobs-succ');
    const twsStatusTextEl = document.getElementById('tws-status-text');
    const twsConnectionStatusEl = document.getElementById('tws-connection-status');

    const agentSelectEl = document.getElementById('agent-select');
    const chatMessagesEl = document.getElementById('chat-messages');
    const chatInputEl = document.getElementById('chat-input');
    const sendButtonEl = document.getElementById('send-button');
    const wsStatusTextEl = document.getElementById('ws-status-text');
    const websocketStatusEl = document.getElementById('websocket-status');

    // RAG Upload Elements
    const fileInputEl = document.getElementById('file-input');
    const uploadButtonEl = document.getElementById('upload-button');
    const uploadStatusEl = document.getElementById('upload-status');

    let websocket = null;

    // --- UI Update Functions ---
    const updateTWSConnectionStatus = function(isOnline) {
        if (isOnline) {
            twsConnectionStatusEl.classList.remove('offline');
            twsConnectionStatusEl.classList.add('online');
            twsStatusTextEl.textContent = 'Disponível';
        } else {
            twsConnectionStatusEl.classList.remove('online');
            twsConnectionStatusEl.classList.add('offline');
            twsStatusTextEl.textContent = 'Indisponível';
        }
    };

    const updateWebSocketStatus = function(isConnected) {
        if (isConnected) {
            websocketStatusEl.classList.remove('offline');
            websocketStatusEl.classList.add('online');
            wsStatusTextEl.textContent = 'Conectado';
            chatInputEl.disabled = false;
            sendButtonEl.disabled = false;
        } else {
            websocketStatusEl.classList.remove('online');
            websocketStatusEl.classList.add('offline');
            wsStatusTextEl.textContent = 'Desconectado';
            chatInputEl.disabled = true;
            sendButtonEl.disabled = true;
        }
    };

    const addChatMessage = function(sender, message, type = 'message') {
        const messageEl = document.createElement('div');
        messageEl.classList.add('message', sender, type);
        messageEl.textContent = message;
        chatMessagesEl.appendChild(messageEl);
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight; // Auto-scroll
    };

    // --- Data Fetching ---
    const fetchSystemStatus = async function() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            // Update dashboard metrics
            workstationsTotalEl.textContent = data.workstations.length;
            jobsAbendEl.textContent = data.jobs.filter(function(j) { return j.status === 'ABEND'; }).length;
            jobsSuccEl.textContent = data.jobs.filter(function(j) { return j.status === 'SUCC'; }).length;
            updateTWSConnectionStatus(true);
        } catch (error) {
            console.error('Failed to fetch system status:', error);
            updateTWSConnectionStatus(false);
            // Reset metrics on failure
            workstationsTotalEl.textContent = '--';
            jobsAbendEl.textContent = '--';
            jobsSuccEl.textContent = '--';
        }
    };

    const fetchAgents = async function() {
        try {
        // Fetch the list of agents from the correct API path.  The agents
        // router lives under /api/v1/agents/, so call that endpoint rather
        // than the root /api/v1/ which will return 404.
        const response = await fetch('/api/v1/agents/');
            if (!response.ok) throw new Error('Failed to fetch agents');
            const agents = await response.json();

            agentSelectEl.innerHTML = '<option value="">Selecione um agente</option>';
            agents.forEach(function(agent) {
                const option = document.createElement('option');
                option.value = agent.id;
                option.textContent = agent.name;
                agentSelectEl.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to fetch agents:', error);
            agentSelectEl.innerHTML = '<option value="">Falha ao carregar agentes</option>';
        }
    };

    // --- RAG File Upload ---
    const uploadFile = async function() {
        const file = fileInputEl.files[0];
        if (!file) {
            uploadStatusEl.textContent = 'Por favor, selecione um arquivo.';
            uploadStatusEl.className = 'upload-status error';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        uploadStatusEl.textContent = 'Enviando arquivo...';
        uploadStatusEl.className = 'upload-status info';

        try {
            const response = await fetch('/api/rag/upload', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (response.ok) {
                uploadStatusEl.textContent = `Arquivo '${result.filename}' enviado com sucesso!`;
                uploadStatusEl.className = 'upload-status success';
                fileInputEl.value = ''; // Clear the input
            } else {
                throw new Error(result.detail || 'Falha no envio do arquivo.');
            }
        } catch (error) {
            console.error('File upload error:', error);
            uploadStatusEl.textContent = `Erro: ${error.message}`;
            uploadStatusEl.className = 'upload-status error';
        }
    };

    // --- WebSocket Management ---
    const connectWebSocket = function() {
        if (websocket) {
            websocket.close();
        }

        const agentId = agentSelectEl.value;
        if (!agentId) {
            updateWebSocketStatus(false);
            return;
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/ws/${agentId}`;
        websocket = new WebSocket(wsUrl);

        websocket.onopen = function() {
            console.log('WebSocket connection established.');
            updateWebSocketStatus(true);
        };

        websocket.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);

            if (data.type === 'stream') {
                const lastMessage = chatMessagesEl.querySelector('.message.agent:last-child');
                if (lastMessage && !lastMessage.dataset.final) {
                    lastMessage.textContent += data.message;
                } else {
                     addChatMessage(data.sender, data.message);
                }
            } else if (data.type === 'message' && data.is_final) {
                const lastMessage = chatMessagesEl.querySelector('.message.agent:last-child');
                 if (lastMessage && !lastMessage.dataset.final) {
                    lastMessage.textContent = data.message;
                    lastMessage.dataset.final = true;
                } else {
                    addChatMessage(data.sender, data.message);
                }
            } else {
                 addChatMessage(data.sender, data.message, data.type);
            }
        };

        websocket.onclose = function() {
            console.log('WebSocket connection closed.');
            updateWebSocketStatus(false);
            websocket = null;
        };

        websocket.onerror = function(error) {
            console.error('WebSocket error:', error);
            addChatMessage('system', 'Erro na conexão com o WebSocket.', 'error');
            updateWebSocketStatus(false);
        };
    };

    const sendMessage = function() {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            const trimmed = chatInputEl.value.trim();
            // Don't send empty messages
            if (!trimmed) {
                return;
            }
            // Build a structured payload so the server knows how to handle
            // the message.  ``type: 'chat_message'`` triggers the AI agent
            // response on the backend.  Include ``content`` and the
            // selected ``agent_id`` for completeness.
            const payload = {
                type: 'chat_message',
                content: trimmed,
                agent_id: agentSelectEl.value || null
            };
            try {
                websocket.send(JSON.stringify(payload));
            } catch (err) {
                console.error('Failed to send WebSocket payload:', err);
                addChatMessage('system', 'Falha ao enviar mensagem.', 'error');
                return;
            }
            // Reflect the user's message in the chat window immediately
            addChatMessage('user', trimmed);
            chatInputEl.value = '';
        }
    };

    // --- Event Listeners ---
    agentSelectEl.addEventListener('change', connectWebSocket);
    sendButtonEl.addEventListener('click', sendMessage);
    chatInputEl.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });
    uploadButtonEl.addEventListener('click', uploadFile);

    // --- Initial Load ---
    const initializeDashboard = function() {
        fetchSystemStatus();
        fetchAgents();
        setInterval(fetchSystemStatus, 30000); // Refresh status every 30 seconds
    };

    initializeDashboard();
});
