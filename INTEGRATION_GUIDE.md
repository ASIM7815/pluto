# PLUTO Frontend ↔ Backend Integration Guide

## 🎯 Quick Start

### 1. Start Backend (Terminal 1)

```bash
cd pluto-backend
chmod +x start.sh
./start.sh
```

Backend will run on **http://127.0.0.1:8765**

### 2. Start Frontend (Terminal 2)

```bash
cd ../  # Back to project root
npm run dev
```

Frontend will run on **http://localhost:3001**

---

## 🔌 Connecting Frontend to Backend

The existing frontend needs minimal changes to connect to the Python backend. Here's what to modify:

### Update `src/services/ai.ts`

Replace the mock `aiService.executeCommand()` with real WebSocket connection:

```typescript
// src/services/ai.ts
export const aiService = {
  ws: null as WebSocket | null,

  connect() {
    this.ws = new WebSocket('ws://127.0.0.1:8765/api/chat/ws');
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const store = usePlutoStore.getState();
      
      // Handle different event types
      switch (data.type) {
        case 'agent_state':
          store.setState(data.state);
          if (data.task) store.setCurrentTask(data.task);
          if (data.error) store.setErrorMessage(data.error);
          break;
          
        case 'execution_step':
          // Update execution steps
          break;
          
        case 'activity':
          store.addActivity(data.activity);
          break;
          
        case 'action_preview':
          store.setActionPreview(data.preview);
          break;
      }
    };
  },

  async executeCommand(command: string) {
    if (!this.ws) this.connect();
    
    this.ws.send(JSON.stringify({
      type: 'command',
      command: command
    }));
  }
};
```

### Update `src/services/voice.ts`

Connect to backend TTS:

```typescript
export const voiceService = {
  async synthesizeSpeech(text: string): Promise<void> {
    const response = await fetch('http://127.0.0.1:8765/api/voice/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    
    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    await audio.play();
  }
};
```

### Update `src/services/system.ts`

Fetch real system metrics:

```typescript
export const systemService = {
  async getMetrics(): Promise<SystemMetrics> {
    const response = await fetch('http://127.0.0.1:8765/api/system/metrics');
    return await response.json();
  },

  async getSystemInfo() {
    const response = await fetch('http://127.0.0.1:8765/api/system/info');
    return await response.json();
  }
};
```

---

## 🧪 Testing the Integration

### Test 1: System Metrics

Visit http://localhost:3001 - the system metrics (CPU, RAM, Storage) should show real values.

### Test 2: Simple Command

Type in command bar:
```
Open VS Code
```

Expected flow:
1. Frontend sends via WebSocket
2. Backend: UNDERSTANDING → THINKING → PLANNING → EXECUTING
3. VS Code launches
4. Activity logged
5. Frontend returns to IDLE

### Test 3: File Operation

```
Create a file called test.txt in ~/Projects
```

Expected:
- File created
- Success state
- Activity shows "File created"

### Test 4: Dangerous Command (Confirmation)

```
Delete my cache files
```

Expected:
- Confirmation dialog appears
- User must approve
- Then execution proceeds

---

## 📡 WebSocket Event Flow

```
FRONTEND                    BACKEND                  
   │                           │
   ├─ command ────────────────>│
   │                           ├─ GPT-OSS
   │                           │
   │<──── agent_state ─────────┤ (understanding)
   │<──── agent_state ─────────┤ (thinking)
   │<──── agent_state ─────────┤ (planning)
   │<──── execution_step ──────┤
   │<──── agent_state ─────────┤ (executing)
   │                           ├─ Execute Tool
   │<──── execution_step ──────┤ (completed)
   │<──── agent_state ─────────┤ (success)
   │<──── activity ────────────┤
   │                           │
```

---

## 🛠️ Available Backend APIs

### REST Endpoints

```
GET  /health                       # Health check
GET  /api/system/metrics           # System metrics
GET  /api/system/info              # System info
POST /api/chat/execute             # Execute command (non-streaming)
POST /api/voice/synthesize         # Text-to-speech
GET  /api/voice/voices             # List voices
POST /api/chat/reset               # Reset agent
```

### WebSocket

```
WS /api/chat/ws                    # Real-time agent communication
```

---

## 🔐 Security Notes

✅ **Backend binds to 127.0.0.1** - Only local access  
✅ **CORS configured** for localhost:3000 and localhost:3001  
✅ **No API keys exposed** to frontend  
✅ **Tool permissions** enforced server-side  
✅ **Path validation** prevents traversal attacks  
✅ **Command classification** blocks dangerous operations  

---

## 🐛 Troubleshooting

### WebSocket connection failed

**Check:**
- Backend is running: `curl http://127.0.0.1:8765/health`
- CORS origins in `.env` include your frontend URL
- No firewall blocking port 8765

### Commands not executing

**Check:**
- WebSocket connected (check browser console)
- Backend logs: `tail -f pluto-backend/logs/*.log`
- API keys valid in `.env`

### Voice not working

**Check:**
- ElevenLabs API key valid
- Voice ID correct (Indian girl voice: `pNInz6obpgDQGcFmaJgB`)
- Audio playback permissions in browser

### Tools failing

**Check:**
- `PLUTO_ALLOWED_PATHS` includes target directory
- File permissions
- Application exists (`which code`, `which firefox`, etc.)

---

## 📈 Next Steps

1. ✅ Backend running
2. ✅ Frontend connected
3. 🔄 Update frontend services to use WebSocket
4. 🧪 Test each command type
5. 🎨 Fine-tune UI based on backend events
6. 🚀 Deploy

---

## 📚 Additional Resources

- FastAPI Docs: https://fastapi.tiangolo.com
- WebSocket Guide: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
- Groq API: https://console.groq.com
- ElevenLabs API: https://elevenlabs.io/docs

---

**PLUTO** - AI that actually controls your computer 🎯
