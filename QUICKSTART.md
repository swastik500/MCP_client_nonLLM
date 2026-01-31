# Quick Start Guide

This guide will help you get the MCP Client up and running in minutes.

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 14 or higher
- Node.js (for running MCP servers)

## Step 1: Install Python Dependencies

```bash
cd client_mcp_hybrid
python -m pip install -r requirements.txt
```

## Step 2: Download spaCy Model

```bash
python -m spacy download en_core_web_sm
```

## Step 3: Setup PostgreSQL Database

### Create Database

```sql
CREATE DATABASE mcp_client;
CREATE USER mcp_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE mcp_client TO mcp_user;
```

### Create Environment File

Create `.env` file in project root:

```env
# Database
DATABASE_URL=postgresql+asyncpg://mcp_user:your_password@localhost/mcp_client

# Security
SECRET_KEY=your-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# App Config
DEBUG=true
LOG_LEVEL=INFO
API_PREFIX=/api/v1
```

## Step 4: Configure MCP Servers

Create `mcp_servers.json` in project root:

```json
{
  "servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:\\Users\\YourUser\\Documents"
      ],
      "env": {}
    },
    {
      "name": "github",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your_github_token_here"
      }
    }
  ]
}
```

### Available MCP Servers

- **filesystem**: `@modelcontextprotocol/server-filesystem`
- **github**: `@modelcontextprotocol/server-github`
- **gitlab**: `@modelcontextprotocol/server-gitlab`
- **google-drive**: `@modelcontextprotocol/server-gdrive`
- **slack**: `@modelcontextprotocol/server-slack`
- **memory**: `@modelcontextprotocol/server-memory`

See [MCP Servers](https://github.com/modelcontextprotocol/servers) for full list.

## Step 5: Run the Application

```bash
python main.py
```

You should see:

```
INFO:     Starting MCP Client v1.0.0
INFO:     Database initialized
INFO:     Discovery complete: 2/2 servers, 15 tools
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 6: Access the Web Interface

Open your browser to: **http://localhost:8000**

### Demo Credentials

- **Admin**: `admin` / `admin`
- **User**: `user` / `user`

## Step 7: Test the System

### Via Web Interface

1. Log in with demo credentials
2. Go to **Execute** page
3. Try example commands:
   - "list all files"
   - "search for readme files"
   - "show recent pull requests"

### Via API

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# Save the token from response
TOKEN="your_token_here"

# Execute command
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "list all files"}'
```

## Troubleshooting

### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:**
1. Check PostgreSQL is running: `pg_ctl status`
2. Verify credentials in `.env`
3. Ensure database exists: `psql -l`

### Module Not Found

```
ModuleNotFoundError: No module named 'spacy'
```

**Solution:**
```bash
python -m pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### MCP Server Discovery Fails

```
ERROR: Discovery failed for server 'filesystem'
```

**Solution:**
1. Test server manually: `npx -y @modelcontextprotocol/server-filesystem .`
2. Check `mcp_servers.json` syntax: `python -m json.tool mcp_servers.json`
3. Ensure Node.js is installed: `node --version`

### Frontend Not Loading

1. Check FastAPI is running on port 8000
2. Verify files exist in `frontend/` directory
3. Check browser console for JavaScript errors
4. Ensure all JS files loaded: auth.js, api.js, utils.js

### Port Already in Use

```
OSError: [Errno 98] Address already in use
```

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill the process or change port in main.py
```

## Next Steps

1. **Add More Servers**: Edit `mcp_servers.json` and restart
2. **Create Custom Rules**: Add business logic rules via database
3. **Train Intent Classifier**: Improve intent classification with training data
4. **Setup Production**: Use PostgreSQL, systemd, nginx (see README.md)

## Common Use Cases

### File Operations

```
"list files in directory X"
"search for files containing 'config'"
"show me recent files"
```

### GitHub Operations

```
"list my pull requests"
"show open issues"
"search repositories for 'python'"
```

### Multi-Step Workflows

```
"find python files and list them"
"search for TODO comments in code"
```

## Need Help?

- Check the [README.md](README.md) for detailed documentation
- Review API docs at http://localhost:8000/docs
- Check logs for error details
- Test MCP servers individually

---

**Happy coding! 🚀**
