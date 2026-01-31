// API client utilities

const API_BASE = '/api/v1';

// Generic API call with auth
async function apiCall(endpoint, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });

    if (response.status === 401) {
        logout();
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || 'Request failed');
    }

    return await response.json();
}

// Execute API
async function executeCommand(input, overrides = null) {
    return await apiCall('/execute', {
        method: 'POST',
        body: JSON.stringify({ input, overrides })
    });
}

// Tools API
async function listTools(serverId = null) {
    const query = serverId ? `?server_id=${serverId}` : '';
    return await apiCall(`/tools${query}`);
}

async function getToolSchema(toolId) {
    return await apiCall(`/tools/${toolId}/schema`);
}

// Servers API
async function listServers() {
    return await apiCall('/servers');
}

async function discoverServers() {
    return await apiCall('/servers/discover', {
        method: 'POST'
    });
}

async function getServerStats(serverId) {
    return await apiCall(`/servers/${serverId}/stats`);
}

// Audit API
async function listAuditLogs(params = {}) {
    const query = new URLSearchParams(params).toString();
    return await apiCall(`/audit/logs${query ? '?' + query : ''}`);
}

async function getAuditDetail(executionId) {
    return await apiCall(`/audit/logs/${executionId}`);
}
