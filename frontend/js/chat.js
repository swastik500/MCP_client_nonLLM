// Universal MCP Client Interface - ES6 Module

// Import all required modules
import { 
    apiCall, 
    executeCommand, 
    listServers, 
    listTools, 
    listAuditLogs, 
    discoverServers 
} from './api.js';

import { 
    isAuthenticated, 
    getCurrentUser, 
    login,
    logout 
} from './auth.js';

import { 
    formatDate, 
    formatDuration, 
    truncate, 
    escapeHtml 
} from './utils.js';

let commandHistory = [];
let currentExecutionId = null;
let availableTools = [];
let availableServers = [];
let auditLogs = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Initializing MCP Universal Interface...');
    
    // Expose functions globally for HTML handlers
    window.logout = logout;
    window.refreshStats = refreshStats;
    window.triggerDiscovery = triggerDiscovery;
    window.sendMessage = sendMessage;
    window.useQuickCommand = useQuickCommand;
    window.useHistoryCommand = useHistoryCommand;
    window.selectTool = selectTool;
    window.filterTools = filterTools;
    window.clearHistory = clearHistory;
    window.showToolsModal = showToolsModal;
    window.showServersModal = showServersModal;
    window.showAuditModal = showAuditModal;
    window.closeModal = closeModal;
    window.clearChat = clearChat;
    window.exportChat = exportChat;
    
    // Wait a bit for all scripts to load
    setTimeout(async () => {
        await initializeInterface();
    }, 100);
    
    // Setup keyboard shortcuts
    const input = document.getElementById('chat-input');
    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        });
    }
});

async function initializeInterface() {
    try {
        // Check authentication first
        if (!isAuthenticated()) {
            showLoginModal();
            return;
        }
        
        // Show authenticated state
        hideLoginModal();
        const user = getCurrentUser();
        document.getElementById('current-user').textContent = user?.username || 'Unknown';
        document.getElementById('system-status').textContent = 'READY';
        
        // Load all data
        await loadInitialData();
        
        addSystemMessage('Universal interface initialized successfully!', 'success');
        
    } catch (error) {
        console.error('Initialization failed:', error);
        addSystemMessage(`Initialization failed: ${error.message}`, 'error');
        if (error.message === 'Unauthorized') {
            showLoginModal();
        }
    }
}

async function loadInitialData() {
    const startTime = Date.now();
    
    try {
        document.getElementById('system-status').textContent = 'LOADING';
        
        // Load servers
        await loadServers();
        
        // Load tools
        await loadTools();
        
        // Load audit logs (if admin)
        await loadAuditLogs();
        
        const duration = Date.now() - startTime;
        document.getElementById('latency').textContent = `${duration} ms`;
        document.getElementById('system-status').textContent = 'READY';
        
    } catch (error) {
        console.error('Failed to load data:', error);
        document.getElementById('system-status').textContent = 'ERROR';
        throw error;
    }
}

async function loadServers() {
    try {
        const serversData = await listServers();
        availableServers = serversData.servers || serversData || [];
        
        const serverCountEl = document.getElementById('server-count');
        if (serverCountEl) {
            serverCountEl.textContent = availableServers.length;
        }
        renderActiveServers(availableServers);
        
    } catch (error) {
        console.error('Failed to load servers:', error);
        const serverCountEl = document.getElementById('server-count');
        if (serverCountEl) {
            serverCountEl.textContent = 'ERR';
        }
        throw error;
    }
}

async function loadTools() {
    try {
        const toolsData = await listTools();
        availableTools = toolsData.tools || toolsData || [];
        
        const toolCountEl = document.getElementById('tool-count');
        if (toolCountEl) {
            toolCountEl.textContent = availableTools.length;
        }
        renderAvailableTools(availableTools);
        
    } catch (error) {
        console.error('Failed to load tools:', error);
        const toolCountEl = document.getElementById('tool-count');
        if (toolCountEl) {
            toolCountEl.textContent = 'ERR';
        }
        throw error;
    }
}

async function loadAuditLogs() {
    try {
        const auditsData = await listAuditLogs({ page_size: 100 });
        auditLogs = auditsData.logs || auditsData || [];
        
        const execCountEl = document.getElementById('execution-count');
        if (execCountEl) {
            execCountEl.textContent = auditLogs.length;
        }
        
    } catch (error) {
        console.log('Audit logs require admin access or are unavailable');
        const execCountEl = document.getElementById('execution-count');
        if (execCountEl) {
            execCountEl.textContent = 'N/A';
        }
    }
}

function renderActiveServers(servers) {
    const container = document.getElementById('active-servers');
    
    container.innerHTML = servers.map(server => `
        <div class="server-item ${server.status === 'active' ? 'active' : server.status === 'error' ? 'error' : ''}">
            <div>
                <div class="server-name">${escapeHtml(server.name)}</div>
                <div style="font-size: 0.7rem; color: #6e7681;">
                    ${server.tools_count || 0} tools • ${escapeHtml(server.transport || 'unknown')}
                </div>
            </div>
            <div class="server-status ${server.status || 'inactive'}">${(server.status || 'inactive').toUpperCase()}</div>
        </div>
    `).join('');
}

function renderAvailableTools(tools) {
    const container = document.getElementById('available-tools');
    const searchTerm = document.getElementById('tool-search')?.value.toLowerCase() || '';
    
    const filteredTools = tools.filter(tool => 
        tool.tool_name.toLowerCase().includes(searchTerm) ||
        (tool.description && tool.description.toLowerCase().includes(searchTerm)) ||
        (tool.category && tool.category.toLowerCase().includes(searchTerm))
    );
    
    container.innerHTML = filteredTools.slice(0, 10).map(tool => `
        <div class="tool-item" onclick="selectTool('${escapeHtml(tool.tool_name)}')">
            <div class="tool-name">${escapeHtml(tool.tool_name)}</div>
            <div class="tool-description">${truncate(escapeHtml(tool.description || ''), 60)}</div>
            <div class="tool-server">📡 ${escapeHtml(tool.server_name || 'Unknown')}</div>
        </div>
    `).join('');
}

function selectTool(toolName) {
    const input = document.getElementById('chat-input');
    input.value = `use ${toolName} `;
    input.focus();
}

function filterTools() {
    renderAvailableTools(availableTools);
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
        // Handle special commands
        if (message.toLowerCase() === 'help') {
            showHelpMessage();
            setPipelineStatus('READY');
            return;
        }
        
        if (message.toLowerCase().includes('refresh') || message.toLowerCase().includes('reload')) {
            await refreshStats();
            addSystemMessage('Data refreshed successfully!', 'success');
            setPipelineStatus('READY');
            return;
        }
        
        // Execute command
        const result = await executeCommand(message);
        
        const duration = Date.now() - startTime;
        document.getElementById('latency').textContent = `${duration} ms`;
        
        // Update pipeline with results
        updatePipeline(result);
        
        // Add system response to chat
        addSystemResponse(result);
        
        setPipelineStatus('READY');
        
        // Refresh stats after successful execution
        await refreshStats();
        
    } catch (error) {
        const duration = Date.now() - startTime;
        document.getElementById('latency').textContent = `${duration} ms`;
        
        // Extract proper error message
        let errorMessage;
        if (typeof error === 'string') {
            errorMessage = error;
        } else if (error?.message) {
            errorMessage = error.message;
        } else if (error?.detail) {
            errorMessage = error.detail;
        } else {
            errorMessage = 'Unknown error occurred';
        }
        
        addErrorMessage(errorMessage);
        setPipelineStatus('ERROR');
        updatePipelineError(errorMessage);
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

function addSystemMessage(message, type = 'info') {
    const messagesContainer = document.getElementById('chat-messages');
    const messageEl = document.createElement('div');
    messageEl.className = `message system-message ${type}-message`;
    
    const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : '🤖';
    
    messageEl.innerHTML = `
        <div class="message-icon">${icon}</div>
        <div class="message-content">
            <strong>[SYSTEM]</strong>
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
    
    const icon = result.status === 'success' ? '✅' : '❌';
    const statusText = result.status.toUpperCase();
    
    messageEl.innerHTML = `
        <div class="message-icon">${icon}</div>
        <div class="message-content">
            <strong>[EXECUTION RESULT]</strong>
            <div class="execution-result ${result.status === 'error' ? 'error' : ''}">
                <div class="result-header">
                    <span>Tool Execution</span>
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

function addErrorMessage(error) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageEl = document.createElement('div');
    messageEl.className = 'message error-message';
    
    // Extract proper error message
    let errorMessage;
    if (typeof error === 'string') {
        errorMessage = error;
    } else if (error?.message) {
        errorMessage = error.message;
    } else if (error?.detail) {
        errorMessage = error.detail;
    } else if (error?.error) {
        errorMessage = error.error;
    } else {
        errorMessage = 'Unknown error occurred';
    }
    
    messageEl.innerHTML = `
        <div class="message-icon">⚠️</div>
        <div class="message-content">
            <strong>[ERROR]</strong>
            <p style="color: #f85149;">${escapeHtml(errorMessage)}</p>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showHelpMessage() {
    const messagesContainer = document.getElementById('chat-messages');
    const messageEl = document.createElement('div');
    messageEl.className = 'message system-message';
    messageEl.innerHTML = `
        <div class="message-icon">❓</div>
        <div class="message-content">
            <strong>[HELP]</strong>
            <div class="help-message">
                <h4>Available Commands & Features:</h4>
                <div class="help-commands">
                    <div class="help-command">
                        <div class="help-command-name">list all tools</div>
                        <div class="help-command-desc">Show all available MCP tools</div>
                    </div>
                    <div class="help-command">
                        <div class="help-command-name">show server status</div>
                        <div class="help-command-desc">Display MCP server information</div>
                    </div>
                    <div class="help-command">
                        <div class="help-command-name">list files</div>
                        <div class="help-command-desc">List files using filesystem server</div>
                    </div>
                    <div class="help-command">
                        <div class="help-command-name">take screenshot</div>
                        <div class="help-command-desc">Take a webpage screenshot</div>
                    </div>
                    <div class="help-command">
                        <div class="help-command-name">refresh / reload</div>
                        <div class="help-command-desc">Refresh system data</div>
                    </div>
                    <div class="help-command">
                        <div class="help-command-name">use [tool_name]</div>
                        <div class="help-command-desc">Execute specific tool directly</div>
                    </div>
                </div>
                <p style="margin-top: 1rem; color: #8b949e; font-style: italic;">
                    💡 Tip: Click any tool in the sidebar to auto-fill the command, or use the quick action buttons below the input.
                </p>
            </div>
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

function clearHistory() {
    commandHistory = [];
    renderHistory();
    addSystemMessage('Command history cleared.', 'info');
}

// Login Modal Functions
function showLoginModal() {
    document.getElementById('login-modal').classList.remove('hidden');
    document.getElementById('modal-username').focus();
    
    // Setup form submission
    const form = document.getElementById('login-form');
    form.onsubmit = async (e) => {
        e.preventDefault();
        await handleLogin();
    };
}

function hideLoginModal() {
    document.getElementById('login-modal').classList.add('hidden');
}

async function handleLogin() {
    const username = document.getElementById('modal-username').value;
    const password = document.getElementById('modal-password').value;
    const errorEl = document.getElementById('login-error');
    
    try {
        const response = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('token', data.access_token);
            localStorage.setItem('user', JSON.stringify(data.user));
            
            hideLoginModal();
            await initializeInterface();
        } else {
            const error = await response.json();
            errorEl.textContent = error.detail || 'Login failed';
            errorEl.classList.remove('hidden');
        }
    } catch (error) {
        errorEl.textContent = 'Network error';
        errorEl.classList.remove('hidden');
    }
}

// Modal Functions
function showToolsModal() {
    const modal = document.getElementById('tools-modal');
    const body = document.getElementById('tools-list');
    
    body.innerHTML = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Tool Name</th>
                    <th>Description</th>
                    <th>Server</th>
                    <th>Category</th>
                </tr>
            </thead>
            <tbody>
                ${availableTools.map(tool => `
                    <tr>
                        <td><strong>${escapeHtml(tool.tool_name)}</strong></td>
                        <td>${truncate(escapeHtml(tool.description || ''), 100)}</td>
                        <td><span class="status-badge active">${escapeHtml(tool.server_name || 'Unknown')}</span></td>
                        <td>${escapeHtml(tool.category || 'General')}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    
    modal.classList.remove('hidden');
}

function showServersModal() {
    const modal = document.getElementById('servers-modal');
    const body = document.getElementById('servers-list');
    
    body.innerHTML = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Server Name</th>
                    <th>Status</th>
                    <th>Transport</th>
                    <th>Tools Count</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
                ${availableServers.map(server => `
                    <tr>
                        <td><strong>${escapeHtml(server.name)}</strong></td>
                        <td><span class="status-badge ${server.status || 'inactive'}">${(server.status || 'inactive').toUpperCase()}</span></td>
                        <td>${escapeHtml(server.transport || 'Unknown')}</td>
                        <td>${server.tools_count || 0}</td>
                        <td>${truncate(escapeHtml(server.description || ''), 100)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    
    modal.classList.remove('hidden');
}

function showAuditModal() {
    const modal = document.getElementById('audit-modal');
    const body = document.getElementById('audit-list');
    
    if (auditLogs.length === 0) {
        body.innerHTML = '<p style="color: #8b949e; text-align: center; padding: 2rem;">No audit logs available or insufficient permissions.</p>';
    } else {
        body.innerHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Input</th>
                        <th>Tool</th>
                        <th>Status</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody>
                    ${auditLogs.slice(0, 50).map(log => `
                        <tr>
                            <td>${formatDate(log.created_at)}</td>
                            <td>${truncate(escapeHtml(log.input_text || ''), 50)}</td>
                            <td><strong>${escapeHtml(log.tool_name || 'N/A')}</strong></td>
                            <td><span class="status-badge ${log.execution_status === 'success' ? 'success' : 'error'}">${(log.execution_status || 'unknown').toUpperCase()}</span></td>
                            <td>${log.execution_duration_ms ? formatDuration(log.execution_duration_ms) : 'N/A'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }
    
    modal.classList.remove('hidden');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
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
        const resultEl = document.getElementById(`${stage}-result`);
        if (stageEl) {
            stageEl.className = 'pipeline-stage';
        }
        if (resultEl) {
            resultEl.textContent = '';
        }
    });
}

function updatePipeline(result) {
    // NLP Stage
    const nlpStage = document.getElementById('stage-nlp');
    const nlpTokens = document.getElementById('nlp-tokens');
    const nlpResult = document.getElementById('nlp-result');
    
    if (nlpStage) nlpStage.classList.add('success');
    if (nlpTokens) nlpTokens.textContent = result.input?.split(' ').length || 0;
    if (nlpResult) nlpResult.textContent = `Entities: ${JSON.stringify(result.entities || {})}`;
    
    // Intent Stage
    const intentStage = document.getElementById('stage-intent');
    const intentRule = document.getElementById('intent-rule');
    const intentResult = document.getElementById('intent-result');
    
    if (intentStage) intentStage.classList.add('success');
    if (intentRule) intentRule.textContent = result.intent || 'auto-detected';
    if (intentResult) intentResult.textContent = `MATCHED: ${result.tool_name || 'unknown'}`;
    
    // Validation Stage
    const validationStage = document.getElementById('stage-validation');
    const validationResult = document.getElementById('validation-result');
    
    if (validationStage) validationStage.classList.add('success');
    if (validationResult) validationResult.textContent = 'INPUT MATCHES TOOL SCHEMA';
    
    // Execution Stage
    const execStage = document.getElementById('stage-execution');
    const execServer = document.getElementById('exec-server');
    const execResult = document.getElementById('exec-result');
    
    if (execStage) execStage.classList.add(result.status === 'success' ? 'success' : 'error');
    if (execServer) execServer.textContent = result.server_name || '--';
    if (execResult) execResult.textContent = `POST ${result.tool_name || 'unknown'}`;
    
    // Response Stage
    const responseStage = document.getElementById('stage-response');
    const responseStatus = document.getElementById('response-status');
    const responseResult = document.getElementById('response-result');
    
    if (responseStage) responseStage.classList.add(result.status === 'success' ? 'success' : 'error');
    if (responseStatus) responseStatus.textContent = result.status === 'success' ? '200 OK' : '500 ERROR';
    if (responseResult) responseResult.textContent = result.status === 'success' ? 'Success' : (result.error || 'Failed');
    
    // Metadata
    const metaServer = document.getElementById('meta-server');
    if (metaServer) metaServer.textContent = result.server_name || '--';
}

function updatePipelineError(error) {
    const stages = ['nlp', 'intent', 'validation', 'execution', 'response'];
    stages.forEach(stage => {
        const stageEl = document.getElementById(`stage-${stage}`);
        if (stageEl) {
            stageEl.classList.add('error');
        }
    });
    
    // Extract proper error message
    let errorMessage;
    if (typeof error === 'string') {
        errorMessage = error;
    } else if (error?.message) {
        errorMessage = error.message;
    } else if (error?.detail) {
        errorMessage = error.detail;
    } else if (error?.error) {
        errorMessage = error.error;
    } else {
        errorMessage = 'Unknown error occurred';
    }
    
    const responseResult = document.getElementById('response-result');
    if (responseResult) {
        responseResult.textContent = errorMessage;
    }
}

// Utility Functions
async function refreshStats() {
    try {
        await loadInitialData();
        addSystemMessage('System data refreshed successfully.', 'success');
    } catch (error) {
        addSystemMessage(`Failed to refresh data: ${error.message}`, 'error');
    }
}

async function triggerDiscovery() {
    try {
        addSystemMessage('Discovering MCP servers...', 'info');
        await apiCall('/servers/discover', { method: 'POST' });
        await loadServers();
        await loadTools();
        addSystemMessage('Server discovery completed.', 'success');
    } catch (error) {
        addSystemMessage(`Server discovery failed: ${error.message}`, 'error');
    }
}

function clearChat() {
    const messagesContainer = document.getElementById('chat-messages');
    messagesContainer.innerHTML = `
        <div class="system-message">
            <div class="message-icon">🤖</div>
            <div class="message-content">
                <strong>SYSTEM</strong>
                <p>Chat cleared. Universal interface ready.</p>
            </div>
        </div>
    `;
}

function exportChat() {
    const messages = document.getElementById('chat-messages').innerText;
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const blob = new Blob([messages], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mcp-chat-export-${timestamp}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}
