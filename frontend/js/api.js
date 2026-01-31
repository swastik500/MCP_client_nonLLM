// API client utilities - ES6 Module

export const API_BASE = '/api/v1';

// Get auth token
function getToken() {
    return localStorage.getItem('token');
}

// Generic API call with auth
export async function apiCall(endpoint, options = {}) {
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
        // Handle logout in the calling module
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || 'Request failed');
    }

    return await response.json();
}

// Execute API
export async function executeCommand(input, overrides = null) {
    return await apiCall('/execute', {
        method: 'POST',
        body: JSON.stringify({ input_text: input, overrides })
    });
}

// Tools API
export async function listTools(serverId = null) {
    const query = serverId ? `?server_id=${serverId}` : '';
    return await apiCall(`/tools${query}`);
}

export async function getToolSchema(toolId) {
    return await apiCall(`/tools/${toolId}/schema`);
}

// Servers API
export async function listServers() {
    return await apiCall('/servers');
}

export async function discoverServers() {
    return await apiCall('/servers/discover', {
        method: 'POST'
    });
}

export async function getServerStats(serverId) {
    return await apiCall(`/servers/${serverId}/stats`);
}

// Audit API
export async function listAuditLogs(params = {}) {
    const query = new URLSearchParams(params).toString();
    return await apiCall(`/audit/logs${query ? '?' + query : ''}`);
}

export async function getAuditDetail(executionId) {
    return await apiCall(`/audit/logs/${executionId}`);
}
