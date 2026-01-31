// Authentication utilities - ES6 Module

const TOKEN_KEY = 'token';
const USER_KEY = 'user';

// Login function
export async function login(username, password) {
    const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();
    
    // Store auth data
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    
    return data;
}

// Logout user
export function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.location.href = 'login.html';
}

// Check if authenticated
export function isAuthenticated() {
    return !!localStorage.getItem(TOKEN_KEY);
}

// Get current user
export function getCurrentUser() {
    const userStr = localStorage.getItem(USER_KEY);
    if (!userStr || userStr === 'undefined' || userStr === 'null') {
        return null;
    }
    try {
        return JSON.parse(userStr);
    } catch (error) {
        console.error('Failed to parse user data:', error);
        return null;
    }
}

// Get auth token
export function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

// Protect page (redirect to login if not authenticated)
export function protectPage() {
    if (!isAuthenticated()) {
        window.location.href = 'login.html';
    }
}

// Render header
export function renderHeader() {
    const header = document.getElementById('header');
    if (!header) return;

    const user = getCurrentUser();
    const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';

    header.innerHTML = `
        <div class="header-container">
            <div class="header-logo">
                <h1>MCP Client</h1>
                <p>Schema-Driven Execution</p>
            </div>
            <nav class="header-nav">
                <a href="dashboard.html" class="nav-link ${currentPage === 'dashboard.html' ? 'active' : ''}">🏠 Dashboard</a>
                <a href="chat.html" class="nav-link ${currentPage === 'chat.html' ? 'active' : ''}">💬 Chat Shell</a>
                <a href="execute.html" class="nav-link ${currentPage === 'execute.html' ? 'active' : ''}">⚡ Execute</a>
                <a href="tools.html" class="nav-link ${currentPage === 'tools.html' ? 'active' : ''}">🔧 Tools</a>
                <a href="servers.html" class="nav-link ${currentPage === 'servers.html' ? 'active' : ''}">📡 Servers</a>
                <a href="audit.html" class="nav-link ${currentPage === 'audit.html' ? 'active' : ''}">📋 Audit</a>
            </nav>
            <div class="header-user">
                <div class="user-info">
                    <div class="user-name">${user?.username || 'User'}</div>
                    <div class="user-role">${user?.role || 'guest'}</div>
                </div>
                <button class="btn btn-secondary" onclick="window.logout()">Logout</button>
            </div>
        </div>
    `;
}
