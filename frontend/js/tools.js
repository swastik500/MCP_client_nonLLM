// Tools page logic

let allTools = [];
let filteredTools = [];

async function loadTools() {
    try {
        loading(true);
        allTools = await listTools();
        filteredTools = [...allTools];
        renderTools();
    } catch (error) {
        showError(error.message);
    } finally {
        loading(false);
    }
}

function renderTools() {
    const toolsGrid = document.getElementById('tools-grid');
    
    if (filteredTools.length === 0) {
        toolsGrid.innerHTML = '<p class="text-muted">No tools found</p>';
        return;
    }

    toolsGrid.innerHTML = filteredTools.map(tool => `
        <div class="tool-card">
            <div class="tool-header">
                <h3 class="tool-name">${escapeHtml(tool.name)}</h3>
                <button class="btn btn-sm btn-primary" onclick="viewToolSchema('${tool.id}')">
                    View Schema
                </button>
            </div>
            <p class="tool-description">${escapeHtml(tool.description || 'No description available')}</p>
            <div class="tool-meta">
                <span class="badge badge-secondary">${escapeHtml(tool.server_name || 'Unknown')}</span>
                ${tool.parameter_count ? `<span class="text-muted">${tool.parameter_count} params</span>` : ''}
            </div>
        </div>
    `).join('');

    document.getElementById('tool-count').textContent = `${filteredTools.length} tools`;
}

function searchTools() {
    const query = document.getElementById('search-input').value.toLowerCase();
    filteredTools = allTools.filter(tool => 
        tool.name.toLowerCase().includes(query) ||
        (tool.description && tool.description.toLowerCase().includes(query))
    );
    renderTools();
}

async function viewToolSchema(toolId) {
    try {
        loading(true);
        const schema = await getToolSchema(toolId);
        const tool = allTools.find(t => t.id === toolId);
        
        const modal = document.getElementById('schema-modal');
        const modalContent = document.getElementById('modal-content');
        
        modalContent.innerHTML = `
            <h2>${escapeHtml(tool?.name || 'Tool Schema')}</h2>
            <p>${escapeHtml(tool?.description || '')}</p>
            <h3>Input Schema</h3>
            <pre>${JSON.stringify(schema, null, 2)}</pre>
        `;
        
        modal.style.display = 'block';
    } catch (error) {
        showError(error.message);
    } finally {
        loading(false);
    }
}

function closeModal() {
    document.getElementById('schema-modal').style.display = 'none';
}

// Handle URL parameters for server filter
function handleServerFilter() {
    const urlParams = new URLSearchParams(window.location.search);
    const serverId = urlParams.get('server');
    if (serverId) {
        filteredTools = allTools.filter(tool => tool.server_id === serverId);
        renderTools();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    protectPage();
    renderHeader();
    loadTools().then(handleServerFilter);

    // Setup search
    const searchInput = document.getElementById('search-input');
    searchInput.addEventListener('input', searchTools);

    // Setup modal close
    document.getElementById('modal-close').addEventListener('click', closeModal);
    window.addEventListener('click', (e) => {
        const modal = document.getElementById('schema-modal');
        if (e.target === modal) {
            closeModal();
        }
    });
});
