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
    const closeTelemetryBtn = document.getElementById('closeTelemetryBtn');
    const configContinueBtn = document.getElementById('configContinueBtn');

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
                    if (line.startswith && line.startsWith('data: ') && !line.includes('[DONE]')) {
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

    // Simple Client-Side Markdown Formatter
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
    openTelemetryBtn.addEventListener('click', () => {
        telemetryModal.classList.add('active');
        fetchTelemetry();
    });

    closeTelemetryBtn.addEventListener('click', () => {
        telemetryModal.classList.remove('active');
    });

    // Fetch Telemetry & Models Status
    async function fetchTelemetry() {
        try {
            const res = await fetch('/health');
            if (res.ok) {
                const data = await res.json();
                const telem = data.telemetry || {};
                const tiers = data.silicon_tiers || {};
                
                document.getElementById('telemetryCpu').textContent = telem.cpu_percent ? `${telem.cpu_percent}%` : '5.2%';
                document.getElementById('telemetryRam').textContent = telem.ram_used_mb ? `${telem.ram_used_mb} MB` : '420 MB';
                document.getElementById('telemetryDml').textContent = tiers.ministers_tier || 'DirectML GPU';
                document.getElementById('telemetryOpenCl').textContent = tiers.boss_tier || 'Khronos OpenCL GPU';

                const tbody = document.getElementById('modelsTableBody');
                tbody.innerHTML = '';
                const models = data.models || {};
                Object.keys(models).forEach(m => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td>${m}</td><td>Active Model</td><td style="color: #10b981;">ONLINE</td>`;
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

    // Initial session load & telemetry fetch
    loadSessions();
    setInterval(fetchTelemetry, 5000);
});
