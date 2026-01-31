// Audit page logic

let audits = [];
let filters = {
    status: '',
    dateFrom: '',
    dateTo: '',
    limit: 50
};

async function loadAuditLogs() {
    try {
        loading(true);
        audits = await listAuditLogs(filters);
        renderAuditLogs();
    } catch (error) {
        showError(error.message);
    } finally {
        loading(false);
    }
}

function renderAuditLogs() {
    const tbody = document.querySelector('#audit-table tbody');
    
    if (audits.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-muted text-center">No audit logs found</td></tr>';
        return;
    }

    tbody.innerHTML = audits.map(audit => `
        <tr onclick="viewAuditDetail('${audit.id}')" style="cursor: pointer;">
            <td>${formatDate(audit.created_at)}</td>
            <td>${truncate(escapeHtml(audit.input), 40)}</td>
            <td>${escapeHtml(audit.tool_name || 'N/A')}</td>
            <td>
                <span class="badge badge-${audit.status === 'success' ? 'success' : audit.status === 'error' ? 'danger' : 'warning'}">
                    ${audit.status}
                </span>
            </td>
            <td>${audit.duration_ms ? formatDuration(audit.duration_ms) : 'N/A'}</td>
            <td>${escapeHtml(audit.user_id || 'system')}</td>
        </tr>
    `).join('');

    document.getElementById('audit-count').textContent = `${audits.length} executions`;
}

async function viewAuditDetail(executionId) {
    try {
        loading(true);
        const detail = await getAuditDetail(executionId);
        
        const modal = document.getElementById('detail-modal');
        const modalContent = document.getElementById('modal-content');
        
        modalContent.innerHTML = `
            <h2>Execution Details</h2>
            <div class="detail-section">
                <h3>Basic Information</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <span class="detail-label">Status:</span>
                        <span class="badge badge-${detail.status === 'success' ? 'success' : detail.status === 'error' ? 'danger' : 'warning'}">
                            ${detail.status}
                        </span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Duration:</span>
                        <span class="detail-value">${detail.duration_ms ? formatDuration(detail.duration_ms) : 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Timestamp:</span>
                        <span class="detail-value">${formatDate(detail.created_at)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">User:</span>
                        <span class="detail-value">${escapeHtml(detail.user_id || 'system')}</span>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <h3>Input</h3>
                <pre>${escapeHtml(detail.input)}</pre>
            </div>
            
            <div class="detail-section">
                <h3>Tool Information</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <span class="detail-label">Tool:</span>
                        <span class="detail-value">${escapeHtml(detail.tool_name || 'N/A')}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Server:</span>
                        <span class="detail-value">${escapeHtml(detail.server_name || 'N/A')}</span>
                    </div>
                </div>
            </div>
            
            ${detail.parameters ? `
                <div class="detail-section">
                    <h3>Parameters</h3>
                    <pre>${JSON.stringify(detail.parameters, null, 2)}</pre>
                </div>
            ` : ''}
            
            ${detail.result ? `
                <div class="detail-section">
                    <h3>Result</h3>
                    <pre>${JSON.stringify(detail.result, null, 2)}</pre>
                </div>
            ` : ''}
            
            ${detail.error ? `
                <div class="detail-section">
                    <h3>Error</h3>
                    <pre class="text-danger">${escapeHtml(detail.error)}</pre>
                </div>
            ` : ''}
            
            ${detail.pipeline_trace ? `
                <div class="detail-section">
                    <h3>Pipeline Trace</h3>
                    <pre>${JSON.stringify(detail.pipeline_trace, null, 2)}</pre>
                </div>
            ` : ''}
        `;
        
        modal.style.display = 'block';
    } catch (error) {
        showError(error.message);
    } finally {
        loading(false);
    }
}

function closeModal() {
    document.getElementById('detail-modal').style.display = 'none';
}

function applyFilters() {
    filters = {
        status: document.getElementById('filter-status').value,
        dateFrom: document.getElementById('filter-date-from').value,
        dateTo: document.getElementById('filter-date-to').value,
        limit: parseInt(document.getElementById('filter-limit').value) || 50
    };
    loadAuditLogs();
}

function clearFilters() {
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-date-from').value = '';
    document.getElementById('filter-date-to').value = '';
    document.getElementById('filter-limit').value = '50';
    filters = { status: '', dateFrom: '', dateTo: '', limit: 50 };
    loadAuditLogs();
}

// Handle URL parameters for execution detail
function handleExecutionDetail() {
    const urlParams = new URLSearchParams(window.location.search);
    const executionId = urlParams.get('id');
    if (executionId) {
        viewAuditDetail(executionId);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    protectPage();
    renderHeader();
    loadAuditLogs().then(handleExecutionDetail);

    // Setup modal close
    document.getElementById('modal-close').addEventListener('click', closeModal);
    window.addEventListener('click', (e) => {
        const modal = document.getElementById('detail-modal');
        if (e.target === modal) {
            closeModal();
        }
    });
});
