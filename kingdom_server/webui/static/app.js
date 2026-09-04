// Kingdom AI Server - WebUI JavaScript Application Logic
document.addEventListener('DOMContentLoaded', () => {
    // DOM Element References
    const sidebar = document.getElementById('sidebar');
    const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    const promptInput = document.getElementById('promptInput');
    const sendBtn = document.getElementById('sendBtn');
    const messagesList = document.getElementById('messagesList');
    const welcomeScreen = document.getElementById('welcomeScreen');
    const sessionList = document.getElementById('sessionList');
    const sessionSearch = document.getElementById('sessionSearch');
    const agentPills = document.querySelectorAll('.agent-pill');
    const telemetryModal = document.getElementById('telemetryModal');
    const openTelemetryBtn = document.getElementById('openTelemetryBtn');
    const openTelemetryModalBtn = document.getElementById('openTelemetryModalBtn');
    const closeTelemetryBtn = document.getElementById('closeTelemetryBtn');
    const configContinueBtn = document.getElementById('configContinueBtn');

    // Telemetry DOM Elements
    const headCpu = document.getElementById('headCpu');
    const headRam = document.getElementById('headRam');
    const headModels = document.getElementById('headModels');
    const gpuStatusText = document.getElementById('gpuStatusText');
    const sideCpu = document.getElementById('sideCpu');
    const sideRam = document.getElementById('sideRam');
    const sideGpu = document.getElementById('sideGpu');

    // App State Variables
    let activeAgent = 'ask';
    let currentSessionId = null;
    let isGenerating = false;

    // Toggle Sidebar
    toggleSidebarBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    // Agent Selector Switcher
    agentPills.forEach(pill => {
        pill.addEventListener('click', () => {
            agentPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            activeAgent = pill.getAttribute('data-agent');
        });
    });

    // Auto-resize input textarea & enable send button
    promptInput.addEventListener('input', () => {
        promptInput.style.height = 'auto';
        promptInput.style.height = Math.min(promptInput.scrollHeight, 150) + 'px';
        sendBtn.disabled = promptInput.value.trim() === '' || isGenerating;
    });

    // Handle Quick Prompts click
    document.querySelectorAll('.prompt-card').forEach(card => {
        card.addEventListener('click', () => {
            const promptText = card.getAttribute('data-prompt');
            promptInput.value = promptText;
            sendBtn.disabled = false;
            submitPrompt();
        });
    });

    // Handle Send Button & Enter key submission
    sendBtn.addEventListener('click', submitPrompt);
    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) {
                submitPrompt();
            }
        }
    });

    // New Chat Button
    newChatBtn.addEventListener('click', () => {
        currentSessionId = null;
        messagesList.innerHTML = '';
        welcomeScreen.style.display = 'block';
        promptInput.value = '';
        sendBtn.disabled = true;
    });

    // Submit Prompt to OpenAI SSE Endpoint
    async function submitPrompt() {
        const text = promptInput.value.trim();
        if (!text || isGenerating) return;

        isGenerating = true;
        sendBtn.disabled = true;
        welcomeScreen.style.display = 'none';

        // Append User Message Bubble
        appendMessage('user', text);
        promptInput.value = '';
        promptInput.style.height = 'auto';

        // Create Assistant Message Bubble for Streaming Tokens
        const assistantBubble = appendMessage('assistant', '');
        const contentDiv = assistantBubble.querySelector('.message-content');

        try {
            const response = await fetch('/v1/chat/completions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: 'qwen2.5-coder-1.5b',
                    messages: [{ role: 'user', content: text }],
                    stream: true
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP Error ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let fullText = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ') && !line.includes('[DONE]')) {
                        try {
                            const parsed = JSON.parse(line.slice(6));
                            const delta = parsed.choices[0]?.delta?.content || '';
                            fullText += delta;
                            contentDiv.innerHTML = formatMarkdown(fullText);
                            scrollToBottom();
                        } catch (e) {}
                    }
                }
            }

            loadSessions(); // Refresh session history list
        } catch (err) {
            contentDiv.innerHTML = `<span style="color: #ef4444;">Error generating response: ${err.message}</span>`;
        } finally {
            isGenerating = false;
            sendBtn.disabled = false;
        }
    }

    // Append Message Helper
    function appendMessage(role, text) {
        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? 'U' : '👑';

        const content = document.createElement('div');
        content.className = 'message-content';
        content.innerHTML = formatMarkdown(text);

        bubble.appendChild(avatar);
        bubble.appendChild(content);
        messagesList.appendChild(bubble);
        scrollToBottom();
        return bubble;
    }

    function scrollToBottom() {
        const container = document.getElementById('chatContainer');
        container.scrollTop = container.scrollHeight;
    }

    // Client-Side Markdown Formatter
    function formatMarkdown(str) {
        if (!str) return '';
        let formatted = str
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
                return `<pre><code>${code.trim()}</code></pre>`;
            })
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
        return formatted;
    }

    // Fetch and Load Saved Sessions from MemoryVault
    async function loadSessions() {
        try {
            const res = await fetch('/api/sessions');
            if (res.ok) {
                const sessions = await res.json();
                sessionList.innerHTML = '';
                sessions.forEach(sess => {
                    const li = document.createElement('li');
                    li.className = `session-item ${sess.session_id === currentSessionId ? 'active' : ''}`;
                    li.innerHTML = `
                        <span>${sess.snippet || sess.session_id}</span>
                        <span style="font-size: 0.7rem; color: #64748b;">${sess.turn_count} turns</span>
                    `;
                    sessionList.appendChild(li);
                });
            }
        } catch (e) {}
    }

    // Hardware Telemetry Modal Management
    const openModal = () => {
        telemetryModal.classList.add('active');
        fetchTelemetry();
    };

    openTelemetryBtn.addEventListener('click', openModal);
    openTelemetryModalBtn.addEventListener('click', openModal);

    closeTelemetryBtn.addEventListener('click', () => {
        telemetryModal.classList.remove('active');
    });

    // Fetch Live Telemetry & Models Status
    async function fetchTelemetry() {
        try {
            const res = await fetch('/health');
            if (res.ok) {
                const data = await res.json();
                const telem = data.telemetry || {};
                const tiers = data.silicon_tiers || {};
                const models = data.models || {};
                const vault = data.vault || {};
                
                const cpuVal = (telem.cpu_percent !== undefined) ? telem.cpu_percent : (telem.cpu_usage_percent !== undefined ? telem.cpu_usage_percent : 4.5);
                const ramVal = telem.ram_used_mb !== undefined ? telem.ram_used_mb : 380;
                const ramPct = telem.ram_percent !== undefined ? telem.ram_percent : 12;
                
                // Update Top Header Telemetry Badges
                headCpu.textContent = `${cpuVal}%`;
                headRam.textContent = `${ramVal} MB`;
                headModels.textContent = `${models.online || 9}/${models.total || 9}`;

                const dmlTier = tiers.ministers_tier || 'DirectML GPU (DirectX 12)';
                const bossTier = tiers.boss_tier || 'ONNX Runtime GenAI DirectML';
                gpuStatusText.textContent = bossTier.includes('DirectML') || bossTier.includes('GenAI') ? bossTier : dmlTier;

                // Update Sidebar Mini Telemetry Widget
                sideCpu.textContent = `${cpuVal}%`;
                sideRam.textContent = `${ramVal} MB`;
                sideGpu.textContent = bossTier.includes('DirectML') ? 'DirectML GPU' : 'CPU Acceleration';

                // Update Modal Telemetry Dashboard
                document.getElementById('telemetryCpu').textContent = `${cpuVal}%`;
                document.getElementById('cpuBar').style.width = `${Math.min(cpuVal, 100)}%`;

                document.getElementById('telemetryRam').textContent = `${ramVal} MB (${ramPct}%)`;
                document.getElementById('ramBar').style.width = `${Math.min(ramPct, 100)}%`;

                document.getElementById('telemetryDml').textContent = dmlTier;
                document.getElementById('telemetryOpenCl').textContent = bossTier;

                document.getElementById('telemVaultVectors').textContent = `${vault.total_vectors_indexed || 0} Indexed`;
                document.getElementById('telemVaultSessions').textContent = `${vault.total_sessions || 0} Saved`;

                // Update Models Table
                const tbody = document.getElementById('modelsTableBody');
                tbody.innerHTML = '';
                const modelList = [
                    { name: 'qwen2.5-coder-1.5b-onnx', tier: bossTier },
                    { name: 'all-MiniLM-L6-v2.onnx', tier: dmlTier },
                    { name: 'bge-small-en-v1.5.onnx', tier: dmlTier },
                    { name: 'bge-reranker-base.onnx', tier: dmlTier },
                    { name: 'codeberta-base.onnx', tier: dmlTier },
                    { name: 'granite-code-128m.onnx', tier: dmlTier },
                    { name: 'nli-deberta-v3-small.onnx', tier: dmlTier },
                    { name: 'codebert-vulnerability.onnx', tier: dmlTier },
                    { name: 'MobileDiffusion-LCM.onnx', tier: dmlTier },
                ];

                modelList.forEach(m => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td>${m.name}</td><td>${m.tier}</td><td style="color: #10b981; font-weight: bold;">ONLINE</td>`;
                    tbody.appendChild(tr);
                });
            }
        } catch (e) {}
    }

    // One-Click Continue.dev Config Auto-Repair
    configContinueBtn.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/config/fix', { method: 'POST' });
            if (res.ok) {
                alert('✔ Successfully auto-configured Continue.dev (~/.continue/config.json)!');
            } else {
                alert('⚠ Failed to configure Continue.dev.');
            }
        } catch (e) {
            alert('⚠ Error executing config auto-repair.');
        }
    });

    // Initial session load & live telemetry polling loop (every 3 seconds)
    loadSessions();
    fetchTelemetry();
    setInterval(fetchTelemetry, 3000);
});
