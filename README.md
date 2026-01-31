# MCP Client - Production-Grade Schema-Driven Execution

A deterministic, schema-driven execution engine for Model Context Protocol (MCP) servers. This system requires **zero code changes** to add new tools and uses **no LLMs** in the execution path.

## Architecture

```
┌─────────────────┐
│   User Input    │
└────────┬────────┘
         │
    ┌────▼─────────────┐
    │  1. NLP Module   │  Extract entities (spaCy)
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │ 2. Intent Engine │  Classify intent (ML)
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │ 3. Rule Engine   │  Apply business logic
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │ 4. Tool Registry │  Match tool from DB
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │ 5. Schema Exec   │  Build params from schema
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │ 6. MCP Client    │  Execute on MCP server
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │ 7. Audit Logger  │  Store full trace
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │     Result       │
    └──────────────────┘
```

## Key Features

- **Zero Code Changes**: Add new tools by just registering MCP servers
- **No LLMs**: Fully deterministic execution using schemas only
- **Schema-Driven**: Uses JSON Schema for parameter extraction
- **Full Audit**: Complete execution trace for every request
- **Production-Ready**: PostgreSQL, async, error handling, tests

## Tech Stack

### Backend
- **FastAPI** - High-performance async API
- **PostgreSQL** - Production database with SQLAlchemy
- **spaCy** - NLP for entity extraction
- **scikit-learn** - Intent classification
- **json-logic-py** - Rule engine
- **JSON Schema** - Parameter validation

### Frontend
- **Vanilla HTML/CSS/JavaScript** - No build tools required
- **Modern CSS** - Responsive design with flexbox/grid
- **Fetch API** - REST client
- **JWT Auth** - Token-based authentication

## Quick Start

### 1. Install Dependencies

```bash
cd client_mcp_hybrid
python -m pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Configure Database

Create PostgreSQL database and `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/mcp_client
SECRET_KEY=your-secret-key-here
DEBUG=true
```

### 3. Configure MCP Servers

Create `mcp_servers.json`:

```json
{
  "servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"]
    }
  ]
}
```

### 4. Run Application

```bash
python main.py
```

Access at: **http://localhost:8000**

**Demo Credentials:**
- Username: `admin` / Password: `admin`
- Username: `user` / Password: `user`

## Frontend Pages

### Dashboard (/)
- System statistics
- Active servers
- Recent executions
- Auto-refresh

### Execute (/execute.html)
- Natural language input
- Example commands
- Real-time results
- Parameter display

### Tools (/tools.html)
- Browse all tools
- Search and filter
- View JSON schemas
- Server grouping

### Servers (/servers.html)
- MCP server list
- Status monitoring
- Trigger discovery
- Statistics

### Audit (/audit.html)
- Execution history
- Filter by status/date
- Detailed traces
- Pipeline information

## API Endpoints

### Authentication
```bash
POST /api/v1/auth/login
POST /api/v1/auth/refresh
```

### Execution
```bash
POST /api/v1/execute
# Body: {"input": "list files in /tmp"}
```

### Tools
```bash
GET /api/v1/tools
GET /api/v1/tools/{tool_id}
GET /api/v1/tools/{tool_id}/schema
```

### Servers
```bash
GET /api/v1/servers
POST /api/v1/servers/discover
GET /api/v1/servers/{server_id}/stats
```

### Audit
```bash
GET /api/v1/audit
GET /api/v1/audit/{execution_id}
```

## Project Structure

```
client_mcp_hybrid/
├── main.py                 # FastAPI application
├── requirements.txt        # Dependencies
│
├── config/                 # Configuration
├── database/               # Database models
├── nlp/                    # Entity extraction
├── intent/                 # Intent classification
├── rules/                  # Rule engine
├── registry/               # Tool registry
├── executor/               # Schema executor
├── mcp/                    # MCP client
├── discovery/              # Server discovery
├── audit/                  # Audit logging
├── api/                    # REST API
├── pipeline/               # Pipeline orchestrator
│
├── frontend/               # Web UI (vanilla JS)
│   ├── login.html
│   ├── dashboard.html
│   ├── execute.html
│   ├── tools.html
│   ├── servers.html
│   ├── audit.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── auth.js
│       ├── api.js
│       ├── utils.js
│       ├── dashboard.js
│       ├── execute.js
│       ├── tools.js
│       ├── servers.js
│       └── audit.js
│
└── tests/                  # Test suite
```

## Usage Examples

### Execute Command via API

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "list all files in /tmp"}'
```

### Response

```json
{
  "status": "success",
  "tool_name": "list_directory",
  "server_name": "filesystem",
  "result": {
    "files": ["file1.txt", "file2.txt"]
  },
  "parameters": {
    "path": "/tmp"
  },
  "duration_ms": 156,
  "execution_id": "exec_123"
}
```

## Zero Code Changes Demo

1. **Add new MCP server** to `mcp_servers.json`
2. **Restart application** (or POST to `/api/v1/servers/discover`)
3. **Tools are automatically available** - no code changes!
4. **Execute commands** using new tools immediately

## Testing

```bash
# Run all tests
pytest

# Specific test
pytest tests/test_pipeline.py

# With coverage
pytest --cov=. --cov-report=html
```

## Production Deployment

### Docker

```bash
docker build -t mcp-client .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e SECRET_KEY=... \
  mcp-client
```

### Systemd Service

```ini
[Unit]
Description=MCP Client
After=network.target postgresql.service

[Service]
Type=simple
User=mcp
WorkingDirectory=/opt/mcp-client
Environment="DATABASE_URL=postgresql://..."
ExecStart=/opt/mcp-client/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name mcp.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Development

### Add Custom Rules

```sql
INSERT INTO business_rules (intent, conditions, actions, priority)
VALUES (
    'file_operation',
    '{"and": [{"var": "action"}, {"==": [{"var": "action"}, "read"]}]}',
    '{"require_permission": "read"}',
    100
);
```

### Train Intent Classifier

```python
from intent.classifier import IntentClassifier

classifier = IntentClassifier()
classifier.train(training_data)
classifier.save_model("intent_model.pkl")
```

## Troubleshooting

### Database Connection
```bash
# Check PostgreSQL
sudo systemctl status postgresql

# Test connection
psql -h localhost -U user -d mcp_client
```

### MCP Server Discovery
```bash
# Test server manually
npx -y @modelcontextprotocol/server-filesystem /tmp

# Validate config
python -m json.tool mcp_servers.json
```

### Frontend Issues
- Check browser console for errors
- Verify FastAPI is serving static files
- Ensure all JS files are loaded (auth.js, api.js, utils.js)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

MIT License

---

**Zero code changes • No LLMs • Fully deterministic**
