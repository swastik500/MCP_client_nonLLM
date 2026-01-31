// Chat Shell Logic

let commandHistory = [];
let currentExecutionId = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    protectPage();
    renderHeader();
    loadInitialData();
    
    // Setup keyboard shortcuts
    const input = document.getElementById('chat-input');
    input.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }
    });
});

async function loadInitialData() {
    try {
        // Load servers
        const serversData = await listServers();
        const servers = serversData.servers || serversData || [];
        document.getElementById('server-count').textContent = servers.length;
        
        // Load tools
        const toolsData = await listTools();
        const tools = toolsData.tools || toolsData || [];
        document.getElementById('tool-count').textContent = tools.length;
        renderToolDefinitions(tools);
        renderLoadedTools(tools);
        
        // Load execution count
        const auditsData = await listAuditLogs({ page_size: 100 });
        const audits = auditsData.logs || auditsData || [];
        document.getElementById('execution-count').textContent = audits.length;
        
    } catch (error) {
        console.error('Failed to load initial data:', error);
        // Show error in chat
        addErrorMessage('Failed to load data. Please check authentication.');
    }
}

function renderToolDefinitions(tools) {
    const container = document.getElementById('tool-definitions');
    const topTools = tools.slice(0, 5);
    
    container.innerHTML = topTools.map(tool => `
        <div class="tool-def-item">
            <div class="tool-def-name">${escapeHtml(tool.name)}</div>
            <div class="tool-def-server">${escapeHtml(tool.server_name || 'Unknown')}</div>
        </div>
    `).join('');
}

function renderLoadedTools(tools) {
    const container = document.getElementById('loaded-tools');
    const recentTools = tools.slice(0, 8);
    
    container.innerHTML = recentTools.map(tool => `
        <div class="loaded-tool">
            <span>${escapeHtml(tool.name)}</span>
            <span class="tool-status idle">IDLE</span>
        </div>
    `).join('');
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Clear input
    input.value = '';
    
    // Add user message to chat
    addUserMessage(message);
    
    // Add to command history
    addToHistory(message);
    
    // Show pipeline as active
    setPipelineStatus('EXECUTING');
    resetPipeline();
    
    const startTime = Date.now();
    
    try {
        // Execute command
        const result = await executeCommand(message);
        
        const duration = Date.now() - startTime;
        document.getElementById('latency').textContent = `${duration} ms`;
        
        // Update pipeline with results
        updatePipeline(result);
        
        // Add system response to chat
        addSystemResponse(result);
        
        setPipelineStatus('READY');
        
    } catch (error) {
        const duration = Date.now() - startTime;
        document.getElementById('latency').textContent = `${duration} ms`;
        
        addErrorMessage(error.message);
        setPipelineStatus('ERROR');
        updatePipelineError(error.message);
    }
}

function addUserMessage(message) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageEl = document.createElement('div');
    messageEl.className = 'message user-message';
    messageEl.innerHTML = `
        <div class="message-icon">👤</div>
        <div class="message-content">
            <strong>[USER]</strong>
            <p>${escapeHtml(message)}</p>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addSystemResponse(result) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageEl = document.createElement('div');
    messageEl.className = `message ${result.status === 'success' ? 'success-message' : 'error-message'}`;
    
    const icon = result.status === 'success' ? '✓' : '✗';
    const statusText = result.status.toUpperCase();
    
    messageEl.innerHTML = `
        <div class="message-icon">${icon}</div>
        <div class="message-content">
            <strong>[SYS]</strong>
            <div class="execution-result ${result.status === 'error' ? 'error' : ''}">
                <div class="result-header">
                    <span>Execution Result</span>
                    <span class="result-status ${result.status === 'error' ? 'error' : 'success'}">${statusText}</span>
                </div>
                ${result.status === 'success' ? `
                    <div class="code-block">
                        <pre>${JSON.stringify(result.result, null, 2)}</pre>
                    </div>
                    <p><strong>Tool:</strong> ${escapeHtml(result.tool_name || 'N/A')}</p>
                    <p><strong>Server:</strong> ${escapeHtml(result.server_name || 'N/A')}</p>
                    <p><strong>Duration:</strong> ${formatDuration(result.duration_ms || 0)}</p>
                ` : `
                    <p class="system-info" style="color: #f85149;">${escapeHtml(result.error || 'Execution failed')}</p>
                `}
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(messageEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addErrorMessage(message) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageEl = document.createElement('div');
    messageEl.className = 'message error-message';
    messageEl.innerHTML = `
        <div class="message-icon">⚠</div>
        <div class="message-content">
            <strong>[ERROR]</strong>
            <p style="color: #f85149;">${escapeHtml(message)}</p>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addToHistory(command) {
    const timestamp = new Date().toLocaleTimeString();
    commandHistory.unshift({ command, timestamp });
    
    if (commandHistory.length > 10) {
        commandHistory.pop();
    }
    
    renderHistory();
}

function renderHistory() {
    const container = document.getElementById('command-history');
    container.innerHTML = commandHistory.map(item => `
        <div class="history-item" onclick="useHistoryCommand('${escapeHtml(item.command).replace(/'/g, "\\'")}')">
            <div>${truncate(escapeHtml(item.command), 40)}</div>
            <div class="history-time">${item.timestamp}</div>
        </div>
    `).join('');
}

function useHistoryCommand(command) {
    document.getElementById('chat-input').value = command;
    document.getElementById('chat-input').focus();
}

function useQuickCommand(command) {
    document.getElementById('chat-input').value = command;
    sendMessage();
}

// Pipeline Functions
function setPipelineStatus(status) {
    const statusEl = document.getElementById('pipeline-status');
    statusEl.textContent = status;
    statusEl.className = 'pipeline-status';
    
    if (status === 'EXECUTING') {
        statusEl.style.background = '#1f6feb';
    } else if (status === 'READY') {
        statusEl.style.background = '#238636';
    } else if (status === 'ERROR') {
        statusEl.style.background = '#da3633';
    }
}

function resetPipeline() {
    const stages = ['nlp', 'intent', 'validation', 'execution', 'response'];
    stages.forEach(stage => {
        const stageEl = document.getElementById(`stage-${stage}`);
        stageEl.className = 'pipeline-stage';
        document.getElementById(`${stage}-result`).textContent = '';
    });
}

function updatePipeline(result) {
    // NLP Stage
    const nlpStage = document.getElementById('stage-nlp');
    nlpStage.classList.add('success');
    document.getElementById('nlp-tokens').textContent = result.input?.split(' ').length || 0;
    document.getElementById('nlp-result').textContent = `Entities: ${JSON.stringify(result.entities || {})}`;
    
    // Intent Stage
    const intentStage = document.getElementById('stage-intent');
    intentStage.classList.add('success');
    document.getElementById('intent-rule').textContent = result.intent || 'auto-detected';
    document.getElementById('intent-result').textContent = `MATCHED: ${result.tool_name || 'unknown'}`;
    
    // Validation Stage
    const validationStage = document.getElementById('stage-validation');
    validationStage.classList.add('success');
    document.getElementById('validation-result').textContent = 'INPUT MATCHES TOOL SCHEMA';
    
    // Execution Stage
    const execStage = document.getElementById('stage-execution');
    execStage.classList.add(result.status === 'success' ? 'success' : 'error');
    document.getElementById('exec-server').textContent = result.server_name || '--';
    document.getElementById('exec-result').textContent = `POST ${result.tool_name || 'unknown'}`;
    
    // Response Stage
    const responseStage = document.getElementById('stage-response');
    responseStage.classList.add(result.status === 'success' ? 'success' : 'error');
    document.getElementById('response-status').textContent = result.status === 'success' ? '200 OK' : '500 ERROR';
    document.getElementById('response-result').textContent = result.status === 'success' ? 'Success' : (result.error || 'Failed');
    
    // Metadata
    document.getElementById('meta-server').textContent = result.server_name || '--';
}

function updatePipelineError(error) {
    const stages = ['nlp', 'intent', 'validation', 'execution', 'response'];
    stages.forEach(stage => {
        const stageEl = document.getElementById(`stage-${stage}`);
        stageEl.classList.add('error');
    });
    
    document.getElementById('response-result').textContent = error;
}

// Utility Functions
function clearChat() {
    const messagesContainer = document.getElementById('chat-messages');
    messagesContainer.innerHTML = `
        <div class="system-message">
            <div class="message-icon">🤖</div>
            <div class="message-content">
                <strong>SYSTEM</strong>
                <p>Chat cleared. MCP Client ready.</p>
            </div>
        </div>
    `;
}

function exportChat() {
    const messages = document.getElementById('chat-messages').innerText;
    const blob = new Blob([messages], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mcp-chat-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}
