// Execute page logic

const exampleCommands = [
    "list all github pull requests",
    "get weather for San Francisco",
    "search files containing 'config'",
    "create a new issue in project X",
    "show my calendar for today"
];

async function executeUserCommand() {
    const inputEl = document.getElementById('command-input');
    const input = inputEl.value.trim();

    if (!input) {
        showError('Please enter a command');
        return;
    }

    try {
        loading(true);
        clearResults();

        const result = await executeCommand(input);
        displayResults(result);
        inputEl.value = '';
    } catch (error) {
        showError(error.message);
    } finally {
        loading(false);
    }
}

function clearResults() {
    document.getElementById('execution-results').innerHTML = '';
    document.getElementById('execution-details').innerHTML = '';
}

function displayResults(result) {
    const resultsEl = document.getElementById('execution-results');
    const detailsEl = document.getElementById('execution-details');

    // Show execution status
    const statusBadge = result.status === 'success' ? 
        '<span class="badge badge-success">✓ Success</span>' :
        result.status === 'error' ?
        '<span class="badge badge-danger">✗ Error</span>' :
        '<span class="badge badge-warning">⚠ Partial</span>';

    resultsEl.innerHTML = `
        <div class="result-header">
            <h3>Execution Result</h3>
            ${statusBadge}
        </div>
        <div class="result-content">
            ${result.status === 'success' ? 
                `<pre>${JSON.stringify(result.result, null, 2)}</pre>` :
                `<p class="text-danger">${escapeHtml(result.error || 'Unknown error')}</p>`
            }
        </div>
    `;

    // Show execution details
    detailsEl.innerHTML = `
        <h4>Execution Details</h4>
        <div class="detail-grid">
            <div class="detail-item">
                <span class="detail-label">Tool:</span>
                <span class="detail-value">${escapeHtml(result.tool_name || 'N/A')}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Server:</span>
                <span class="detail-value">${escapeHtml(result.server_name || 'N/A')}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Duration:</span>
                <span class="detail-value">${formatDuration(result.duration_ms || 0)}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Execution ID:</span>
                <span class="detail-value">${escapeHtml(result.execution_id || 'N/A')}</span>
            </div>
        </div>
        ${result.parameters ? `
            <h5>Parameters</h5>
            <pre>${JSON.stringify(result.parameters, null, 2)}</pre>
        ` : ''}
    `;
}

function loadExampleCommands() {
    const examplesEl = document.getElementById('example-commands');
    examplesEl.innerHTML = exampleCommands.map(cmd => `
        <button class="btn btn-secondary btn-sm example-btn" onclick="useExample('${escapeHtml(cmd)}')">
            ${escapeHtml(cmd)}
        </button>
    `).join('');
}

function useExample(command) {
    document.getElementById('command-input').value = command;
}

// Handle Enter key in input
document.addEventListener('DOMContentLoaded', () => {
    protectPage();
    renderHeader();
    loadExampleCommands();

    const inputEl = document.getElementById('command-input');
    inputEl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            executeUserCommand();
        }
    });
});
