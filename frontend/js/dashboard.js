// Dashboard page logic

let refreshInterval = null;

async function loadDashboard() {
    try {
        loading(true);
        await Promise.all([
            loadStats(),
            loadServers(),
            loadRecentExecutions()
        ]);
    } catch (error) {
        showError(error.message);
    } finally {
        loading(false);
    }
}

async function loadStats() {
    const servers = await listServers();
    const tools = await listTools();
    const audits = await listAuditLogs({ limit: 100 });

    // Calculate stats
    const activeServers = servers.filter(s => s.status === 'active').length;
    const totalTools = tools.length;
    const executions = audits.length;
    const successRate = executions > 0 
        ? ((audits.filter(a => a.status === 'success').length / executions) * 100).toFixed(1)
        : '0';

    document.getElementById('stat-servers').textContent = activeServers;
    document.getElementById('stat-tools').textContent = totalTools;
    document.getElementById('stat-executions').textContent = executions;
    document.getElementById('stat-success-rate').textContent = `${successRate}%`;
}

async function loadServers() {
    const servers = await listServers();
    const serverList = document.getElementById('server-list');
    
    if (servers.length === 0) {
        serverList.innerHTML = '<p class="text-muted">No servers configured</p>';
        return;
    }

    serverList.innerHTML = servers.map(server => `
        <div class="server-item">
            <div class="server-info">
                <div class="server-name">${escapeHtml(server.name)}</div>
                <div class="server-meta">
                    <span class="badge badge-${server.status === 'active' ? 'success' : 'secondary'}">
                        ${server.status}
                    </span>
                    <span class="text-muted">${server.tool_count || 0} tools</span>
                </div>
            </div>
            <a href="tools.html?server=${server.id}" class="btn btn-sm btn-primary">View Tools</a>
        </div>
    `).join('');
}

async function loadRecentExecutions() {
    const audits = await listAuditLogs({ limit: 5 });
    const executionList = document.getElementById('recent-executions');
    
    if (audits.length === 0) {
        executionList.innerHTML = '<p class="text-muted">No recent executions</p>';
        return;
    }

    executionList.innerHTML = audits.map(audit => `
        <div class="execution-item" onclick="viewExecutionDetail('${audit.id}')">
            <div class="execution-info">
                <div class="execution-input">${truncate(escapeHtml(audit.input), 60)}</div>
                <div class="execution-meta">
                    <span class="badge badge-${audit.status === 'success' ? 'success' : audit.status === 'error' ? 'danger' : 'warning'}">
                        ${audit.status}
                    </span>
                    <span class="text-muted">${formatRelativeTime(audit.created_at)}</span>
                    ${audit.duration_ms ? `<span class="text-muted">${formatDuration(audit.duration_ms)}</span>` : ''}
                </div>
            </div>
        </div>
    `).join('');
}

function viewExecutionDetail(executionId) {
    window.location.href = `audit.html?id=${executionId}`;
}

function startAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(loadDashboard, 30000); // Refresh every 30s
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    protectPage();
    renderHeader();
    loadDashboard();
    startAutoRefresh();
});

// Cleanup on page unload
window.addEventListener('beforeunload', stopAutoRefresh);
