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

    // RAG Package Elements
    const packageSelectEl = document.getElementById('package-select');
    const ingestButtonEl = document.getElementById('ingest-button');
    const ingestStatusEl = document.getElementById('ingest-status');

    let websocket = null;

    // --- UI Update Functions ---
    /**
     * Update the visual status indicator for the TWS connection.
     *
     * @param {boolean} isOnline - Whether the TWS service is reachable.
     * @param {boolean} [isDegraded=false] - Whether the service is responding but
     *   degraded (e.g. missing some metrics).  When degraded, the status
     *   element receives the ``degraded`` class and shows a warning.
     */
    const updateTWSConnectionStatus = function(isOnline, isDegraded = false) {
        // Clear any previous state classes before applying new ones
        twsConnectionStatusEl.classList.remove('online', 'offline', 'degraded');
        if (isOnline) {
            if (isDegraded) {
                twsConnectionStatusEl.classList.add('degraded');
                twsStatusTextEl.textContent = 'Degradado';
            } else {
                twsConnectionStatusEl.classList.add('online');
                twsStatusTextEl.textContent = 'Disponível';
            }
        } else {
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
    /**
     * Fetch current TWS status from the backend.  This function requests
     * the list of workstations and jobs from dedicated TWS endpoints.  If
     * either call fails, the dashboard enters a degraded state and metrics
     * are reset.  In a mock deployment these endpoints will return empty
     * arrays which are handled gracefully.
     */
    const fetchSystemStatus = async function() {
        try {
            // Fetch workstations and jobs concurrently
            const [wsResp, jobsResp] = await Promise.all([
                fetch('/api/v1/tws/workstations'),
                fetch('/api/v1/tws/jobs'),
            ]);
            if (!wsResp.ok || !jobsResp.ok) {
                throw new Error(`HTTP error! status: ${wsResp.status} ${jobsResp.status}`);
            }
            const workstations = await wsResp.json();
            const jobs = await jobsResp.json();
            // Update metrics: when running in mock mode the arrays may be empty.
            // If either array is missing (non-array) display '--'.
            let wsCount = '--';
            let abendCount = '--';
            let succCount = '--';
            let degraded = false;
            if (Array.isArray(workstations)) {
                wsCount = workstations.length;
                // Consider degraded if there are zero workstations but the call succeeded
                if (workstations.length === 0) {
                    degraded = true;
                }
            }
            if (Array.isArray(jobs)) {
                abendCount = jobs.filter(function(j) { return j.status === 'ABEND'; }).length;
                succCount = jobs.filter(function(j) { return j.status === 'SUCC'; }).length;
                if (jobs.length === 0) {
                    degraded = true;
                }
            }
            workstationsTotalEl.textContent = wsCount;
            jobsAbendEl.textContent = abendCount;
            jobsSuccEl.textContent = succCount;
            // Online if the API responded; degrade if counts are zero but calls succeeded
            updateTWSConnectionStatus(true, degraded);
        } catch (error) {
            console.error('Failed to fetch TWS status:', error);
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
            const response = await fetch('/api/v1/rag/upload', {
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

    // --- Knowledge Package Management ---
    /**
     * Load available knowledge packages from the backend and populate the
     * package selection dropdown.  If no packages are available, an
     * appropriate placeholder is shown.
     */
    const loadKnowledgePackages = async function() {
        try {
            const resp = await fetch('/api/v1/rag/packages');
            if (!resp.ok) throw new Error(`Erro HTTP ${resp.status}`);
            const packages = await resp.json();
            packageSelectEl.innerHTML = '';
            if (Array.isArray(packages) && packages.length > 0) {
                packageSelectEl.innerHTML = '<option value="">Selecione um pacote</option>';
                packages.forEach(function(pkg) {
                    const opt = document.createElement('option');
                    opt.value = pkg;
                    opt.textContent = pkg;
                    packageSelectEl.appendChild(opt);
                });
            } else {
                packageSelectEl.innerHTML = '<option value="">Nenhum pacote disponível</option>';
            }
        } catch (error) {
            console.error('Failed to load knowledge packages:', error);
            packageSelectEl.innerHTML = '<option value="">Erro ao carregar pacotes</option>';
        }
    };

    /**
     * Ingest the currently selected knowledge package.  Sends a POST request
     * to the backend.  Displays progress and result messages in the
     * ``ingestStatusEl`` element.
     */
    const ingestSelectedPackage = async function() {
        const pkg = packageSelectEl.value;
        if (!pkg) {
            ingestStatusEl.textContent = 'Selecione um pacote para ingestão.';
            ingestStatusEl.className = 'upload-status error';
            return;
        }
        ingestStatusEl.textContent = 'Iniciando ingestão...';
        ingestStatusEl.className = 'upload-status info';
        try {
            const resp = await fetch(`/api/v1/rag/packages/${encodeURIComponent(pkg)}/ingest`, {
                method: 'POST',
            });
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || `Erro ${resp.status}`);
            }
            ingestStatusEl.className = 'upload-status success';
            ingestStatusEl.textContent = data.message || `Ingestado ${data.indexed} arquivos.`;
        } catch (error) {
            console.error('Failed to ingest package:', error);
            ingestStatusEl.className = 'upload-status error';
            ingestStatusEl.textContent = error.message;
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
    ingestButtonEl.addEventListener('click', ingestSelectedPackage);

    // --- Initial Load ---
    const initializeDashboard = function() {
        fetchSystemStatus();
        fetchAgents();
        loadKnowledgePackages();
        setInterval(fetchSystemStatus, 30000); // Refresh status every 30 seconds
    };

    initializeDashboard();
});
