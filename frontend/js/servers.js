// Servers page logic

let servers = [];

async function loadServers() {
    try {
        loading(true);
        servers = await listServers();
        renderServers();
    } catch (error) {
        showError(error.message);
    } finally {
        loading(false);
    }
}

function renderServers() {
    const serverList = document.getElementById('server-list');
    
    if (servers.length === 0) {
        serverList.innerHTML = '<p class="text-muted">No servers configured. Click "Discover Servers" to start.</p>';
        return;
    }

    serverList.innerHTML = servers.map(server => `
        <div class="server-card">
            <div class="server-header">
                <div>
                    <h3 class="server-name">${escapeHtml(server.name)}</h3>
                    <p class="server-command">${escapeHtml(server.command || 'N/A')}</p>
                </div>
                <span class="badge badge-${server.status === 'active' ? 'success' : 'secondary'}">
                    ${server.status}
                </span>
            </div>
            <div class="server-stats">
                <div class="stat-item">
                    <span class="stat-label">Tools:</span>
                    <span class="stat-value">${server.tool_count || 0}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Last Sync:</span>
                    <span class="stat-value">${server.last_sync ? formatRelativeTime(server.last_sync) : 'Never'}</span>
                </div>
            </div>
            <div class="server-actions">
                <button class="btn btn-primary btn-sm" onclick="viewServerTools('${server.id}')">
                    View Tools
                </button>
                <button class="btn btn-secondary btn-sm" onclick="viewServerStats('${server.id}')">
                    Statistics
                </button>
            </div>
        </div>
    `).join('');

    document.getElementById('server-count').textContent = `${servers.length} servers`;
}

async function discoverNewServers() {
    try {
        loading(true);
        const result = await discoverServers();
        showSuccess(`Discovered ${result.discovered || 0} new servers`);
        await loadServers();
    } catch (error) {
        showError(error.message);
    } finally {
        loading(false);
    }
}

function viewServerTools(serverId) {
    window.location.href = `tools.html?server=${serverId}`;
}

async function viewServerStats(serverId) {
    try {
        loading(true);
        const stats = await getServerStats(serverId);
        const server = servers.find(s => s.id === serverId);
        
        const modal = document.getElementById('stats-modal');
        const modalContent = document.getElementById('modal-content');
        
        modalContent.innerHTML = `
            <h2>${escapeHtml(server?.name || 'Server Statistics')}</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Tools</div>
                    <div class="stat-value">${stats.tool_count || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Executions</div>
                    <div class="stat-value">${stats.execution_count || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Success Rate</div>
                    <div class="stat-value">${stats.success_rate ? (stats.success_rate * 100).toFixed(1) + '%' : 'N/A'}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Avg Duration</div>
                    <div class="stat-value">${stats.avg_duration_ms ? formatDuration(stats.avg_duration_ms) : 'N/A'}</div>
                </div>
            </div>
        `;
        
        modal.style.display = 'block';
    } catch (error) {
        showError(error.message);
    } finally {
        loading(false);
    }
}

function closeModal() {
    document.getElementById('stats-modal').style.display = 'none';
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    protectPage();
    renderHeader();
    loadServers();

    // Setup modal close
    document.getElementById('modal-close').addEventListener('click', closeModal);
    window.addEventListener('click', (e) => {
        const modal = document.getElementById('stats-modal');
        if (e.target === modal) {
            closeModal();
        }
    });
});
