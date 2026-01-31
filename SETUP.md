# MCP Client - Complete Setup Guide

## Quick Start (5 minutes)

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or use SQLite for testing)

### Windows Quick Start

```powershell
# 1. Backend setup
python -m venv venv
venv\Scripts\activate
pip install -r config\requirements.txt
python -m spacy download en_core_web_sm

# 2. Configure (optional - defaults work for testing)
# Edit config/settings.py if needed

# 3. Run migration to fix database schema
python migrate_db.py

# 4. Start application
python main.py

# 5. Open browser
# http://localhost:8000
```

### Linux/macOS Quick Start

```bash
# 1. Backend setup
python -m venv venv
source venv/bin/activate
pip install -r config/requirements.txt
python -m spacy download en_core_web_sm

# 2. Configure (optional - defaults work for testing)
# Edit config/settings.py if needed

# 3. Run migration to fix database schema
python migrate_db.py

# 4. Start application
python main.py

# 5. Open browser
# http://localhost:8000
```

## Or Use The Automated Script

### Windows
```powershell
.\start.bat
```

### Linux/macOS
```bash
chmod +x start.sh
./start.sh
```

## Project Structure

```
client_mcp_hybrid/
├── frontend/              # Vanilla HTML/CSS/JS frontend
│   ├── login.html        # Login page
│   ├── dashboard.html    # System dashboard
│   ├── execute.html      # Command execution
│   ├── tools.html        # Tool browser
│   ├── servers.html      # Server management
│   ├── audit.html        # Execution history
│   ├── css/
│   │   └── style.css     # Complete styling
│   └── js/
│       ├── auth.js       # Authentication
│       ├── api.js        # REST API client
│       ├── utils.js      # Helper functions
│       ├── dashboard.js  # Dashboard logic
│       ├── execute.js    # Execute page logic
│       ├── tools.js      # Tools page logic
│       ├── servers.js    # Servers page logic
│       └── audit.js      # Audit page logic
├── config/               # Backend configuration
│   ├── settings.py       # Centralized settings
│   ├── mcp_servers.json  # MCP server definitions
│   └── requirements.txt  # Python dependencies
├── database/             # Database layer
├── nlp/                  # Entity extraction
├── intent/               # Intent classification
├── rules/                # Rule engine
├── registry/             # Tool registry
├── executor/             # Schema executor
├── mcp/                  # MCP protocol client
├── discovery/            # Tool discovery
├── api/                  # FastAPI routes
├── pipeline/             # Execution pipeline
├── tests/                # Test suite
└── main.py               # Application entry point
```

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│  Vanilla HTML + CSS + JavaScript                            │
│  http://localhost:8000                                       │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTP/REST API
                     │
┌────────────────────▼─────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  http://localhost:8000                                       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         8-Stage Deterministic Pipeline               │  │
│  │                                                      │  │
│  │  1. Entity Extraction (spaCy)                       │  │
│  │  2. Intent Classification (ML + overrides)          │  │
│  │  3. Rule Evaluation (json-logic)                    │  │
│  │  4. Tool Selection (registry lookup)                │  │
│  │  5. Parameter Building (schema-driven)              │  │
│  │  6. Schema Validation (JSON Schema)                 │  │
│  │  7. Tool Execution (MCP transport)                  │  │
│  │  8. Response Formatting                             │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     │ MCP Protocol (stdio/HTTP/WS)
                     │
┌────────────────────▼─────────────────────────────────────────┐
│                    MCP Servers                               │
│  - Filesystem Server                                         │
│  - Fetch Server                                              │
│  - Memory Server                                             │
│  - Custom Servers...                                         │
└──────────────────────────────────────────────────────────────┘
```

## Features

### Backend (Python)
- ✅ **Zero-code tool addition** - Just update config/mcp_servers.json
- ✅ **No LLMs** - Fully deterministic execution
- ✅ **Schema-driven** - All tools defined by JSON schemas
- ✅ **8-stage pipeline** - Transparent, auditable execution
- ✅ **Full audit trail** - Every execution logged to database
- ✅ **JWT authentication** - Secure API access
- ✅ **Rule engine** - Fine-grained permissions & thresholds

### Frontend (Vanilla JS)
- 🎨 **Modern UI** - Clean, responsive design with modern CSS
- 🔐 **Authentication** - Login with JWT tokens
- ⚡ **Execute Interface** - Natural language command input
- 🔧 **Tool Browser** - Explore all discovered tools & schemas
- 🖥️ **Server Management** - Monitor MCP servers, trigger discovery
- 📊 **Audit Log** - Complete execution history with filters
- 📱 **Responsive** - Works on desktop, tablet, and mobile
- 🚀 **No Build Tools** - Just HTML/CSS/JS, no npm/webpack needed

## Default Login Credentials

For testing purposes:

- **Admin**: `admin` / `admin`
- **User**: `user` / `user`
- **Guest**: `guest` / `guest`

⚠️ **Change these in production!**

## Configuration

### Backend Environment Variables

Create a `.env` file:

```bash
# Database (optional - defaults to SQLite)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/mcp_client

# JWT Secret (change in production!)
JWT_SECRET_KEY=your-secret-key-change-this-in-production

# Debug mode
DEBUG=false
LOG_LEVEL=INFO

# MCP Servers config
MCP_SERVERS_CONFIG=config/mcp_servers.json
```

### Adding New MCP Servers

Edit `config/mcp_servers.json`:

```json
{
  "servers": [
    {
      "id": "my-custom-server",
      "name": "My Custom MCP Server",
      "transport_type": "stdio",
      "command": "python",
      "args": ["-m", "my_mcp_server"],
      "enabled": true
    }
  ]
}
```

**That's it! No code changes needed.**

Restart the backend and your new server's tools will be automatically discovered.

## Testing

```bash
# Backend tests
pytest tests/ -v

# Test zero-code changes constraint
pytest tests/test_zero_code_changes.py -v
```

## Troubleshooting

### Port Already in Use

**Backend (8000):**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :8000
kill -9 <PID>
```

**Frontend (3000):**
```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :3000
kill -9 <PID>
```

### Database Connection Issues

For testing, the system defaults to SQLite (no setup needed).

For PostgreSQL:
```bash
# Create database
createdb mcp_client

# Set environment variable
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/mcp_client"
```

### Frontend API Proxy Issues

The frontend is served directly by FastAPI at port 8000. Ensure:
1. Backend is running on port 8000
2. All HTML/CSS/JS files are in the `frontend/` directory

### spaCy Model Not Found

```bash
python -m spacy download en_core_web_sm
```

## Production Deployment

### Backend

```bash
# Use production WSGI server
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

Frontend is automatically served by the FastAPI backend.

### Docker (Optional)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY config/requirements.txt .
RUN pip install -r requirements.txt
RUN python -m spacy download en_core_web_sm
COPY . .
CMD ["python", "main.py"]
```

## Key Architectural Decisions

### Why No LLMs?
- **Deterministic**: Same input → same output
- **Auditable**: Every decision is traceable
- **Cost-effective**: No API fees
- **Predictable**: No hallucinations or errors

### Why Schema-Driven?
- **Zero-code**: Add tools without changing Python
- **Self-documenting**: Schemas define everything
- **Validated**: JSON Schema ensures correctness
- **MCP-native**: Leverage existing MCP infrastructure

### Why 8 Stages?
- **Transparent**: Each stage has clear responsibility
- **Debuggable**: Inspect state at any point
- **Extensible**: Add stages without breaking others
- **Auditable**: Complete execution trace

## Support & Resources

- **Backend Docs**: See main README.md
- **API Docs**: http://localhost:8000/docs (when running)
- **MCP Protocol**: https://modelcontextprotocol.io

## License

MIT
