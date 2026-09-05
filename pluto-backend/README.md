# PLUTO Backend - Python FastAPI Agent

🤖 **PLUTO** is a futuristic AI desktop assistant that controls your Linux computer through natural language using GPT-OSS (Groq), ElevenLabs voice, and a secure Python backend.

## Architecture

```
Frontend (Next.js) ←→ Backend (FastAPI) ←→ GPT-OSS / ElevenLabs
                            ↓
                       Tool Registry
                            ↓
                    OS Tools (Linux)
```

## Prerequisites

- **Python 3.12+**
- **Linux OS** (Ubuntu/Debian recommended)
- **GPT-OSS API Key** (Groq)
- **ElevenLabs API Key**

## Installation

### 1. Create Virtual Environment

```bash
cd pluto-backend
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
nano .env  # or use any editor
```

**Required Configuration:**
- `GPT_OSS_API_KEY` - Your Groq API key
- `ELEVENLABS_API_KEY` - Your ElevenLabs API key
- `ELEVENLABS_VOICE_ID` - Voice ID (default: Indian girl voice)
- `PLUTO_ALLOWED_PATHS` - Comma-separated allowed directories

### 4. Run Backend

```bash
python -m app.main
```

Or using uvicorn directly:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
```

The backend will start on **http://127.0.0.1:8765**

## Frontend Integration

Make sure your Next.js frontend is configured to connect to the backend:

```bash
cd ../  # Go to frontend directory
npm run dev
```

Frontend should be on **http://localhost:3000** or **http://localhost:3001**

## API Endpoints

### Chat & Commands
- `POST /api/chat/execute` - Execute a command
- `WS /api/chat/ws` - WebSocket for real-time events
- `POST /api/chat/reset` - Reset agent conversation

### Voice
- `POST /api/voice/synthesize` - Text-to-speech
- `GET /api/voice/voices` - List available voices

### System
- `GET /api/system/metrics` - System metrics (CPU, RAM, etc.)
- `GET /api/system/info` - System information
- `GET /api/system/status` - Health check

## Available Tools

The agent has access to these OS capabilities:

### Filesystem
- `create_file` - Create new file
- `read_file` - Read file content
- `list_directory` - List directory contents
- `create_directory` - Create directory
- `delete_file` - Delete file (requires confirmation)

### Applications
- `open_application` - Launch applications (VS Code, Firefox, etc.)
- `open_url` - Open URL in browser

### System
- `get_processes` - List running processes
- `execute_command` - Run terminal commands (requires confirmation)

## Security Features

✅ **Path Validation** - Prevents path traversal attacks  
✅ **Sandbox Filesystem** - Only allowed directories accessible  
✅ **Command Classification** - SAFE/CONFIRM_REQUIRED/BLOCKED  
✅ **Permission System** - Tool-level authorization  
✅ **No Direct Code Execution** - LLM cannot run arbitrary Python  
✅ **Structured Logging** - All operations logged  
✅ **Local-First** - Binds to 127.0.0.1 by default  

## Agent States

The agent communicates these states to frontend:

- `idle` - Ready for commands
- `listening` - Receiving voice input
- `understanding` - Parsing request
- `thinking` - Analyzing with GPT-OSS
- `planning` - Selecting tools
- `executing` - Running OS tools
- `success` - Task completed
- `error` - Something went wrong

## Testing

```bash
pytest tests/
```

## Development

### Project Structure

```
pluto-backend/
├── app/
│   ├── main.py              # FastAPI app
│   ├── api/                 # API routes
│   │   ├── routes_chat.py
│   │   ├── routes_voice.py
│   │   └── routes_system.py
│   ├── core/                # Core utilities
│   │   ├── config.py
│   │   ├── security.py
│   │   └── logging.py
│   ├── agent/               # Agent logic
│   │   ├── orchestrator.py
│   │   └── tool_registry.py
│   ├── llm/                 # LLM clients
│   │   └── gpt_oss.py
│   ├── voice/               # Voice clients
│   │   └── elevenlabs.py
│   ├── tools/               # OS tools
│   │   ├── filesystem.py
│   │   ├── applications.py
│   │   ├── system.py
│   │   └── terminal.py
│   └── schemas/             # Pydantic models
│       ├── chat.py
│       ├── tools.py
│       └── system.py
├── tests/
├── requirements.txt
├── .env
└── README.md
```

### Adding a New Tool

1. **Create tool function** in appropriate file (e.g., `tools/custom.py`)
2. **Register in tool_registry.py**:

```python
tool_registry.register_tool(
    name="my_tool",
    description="What this tool does",
    parameters={...},  # JSON schema
    permission_level="SAFE",  # or "CONFIRM_REQUIRED"
    category="system",
    handler=my_tool_function
)
```

3. Tool is now available to the agent!

## Troubleshooting

### Backend won't start
- Check Python version: `python3 --version` (need 3.12+)
- Verify API keys in `.env`
- Check port 8765 is not in use: `lsof -i :8765`

### Tools not executing
- Check `PLUTO_ALLOWED_PATHS` includes target directory
- Review logs for permission errors
- Verify command classification in `core/security.py`

### Frontend can't connect
- Verify backend is running on 127.0.0.1:8765
- Check CORS origins in `.env` match frontend URL
- Test endpoint: `curl http://127.0.0.1:8765/health`

## License

MIT

## Credits

Built with:
- **FastAPI** - Modern Python web framework
- **GPT-OSS (Groq)** - Llama 3.3 70B LLM
- **ElevenLabs** - Natural voice synthesis
- **psutil** - System monitoring

---

**PLUTO** - Your AI-powered Linux desktop companion 🚀
