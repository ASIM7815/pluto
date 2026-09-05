# 🚀 PLUTO - Quick Start Guide

## ⚠️ API Keys Required

Before starting, you need to configure your API keys in `pluto-backend/.env`:
- GPT-OSS (Groq): Get your key from [console.groq.com](https://console.groq.com)
- ElevenLabs: Get your key from [elevenlabs.io](https://elevenlabs.io)

See `BACKEND_COMPLETE.md` for detailed setup instructions.

---

## 🏃 Start PLUTO (2 Terminals)

### Terminal 1: Start Backend

```bash
cd pluto-backend
chmod +x start.sh
./start.sh
```

**Expected output:**
```
🚀 Starting PLUTO Backend...
✅ Starting PLUTO Agent on http://127.0.0.1:8765
INFO:     Started server process
INFO:     Uvicorn running on http://127.0.0.1:8765
```

Backend is now running! ✅

---

### Terminal 2: Start Frontend

```bash
# From project root
npm run dev
```

**Expected output:**
```
  ▲ Next.js 15.5.25 (Turbopack)
  - Local:        http://localhost:3001
✓ Ready in 1640ms
```

Frontend is now running! ✅

---

## 🧪 Test the Connection

### 1. Open Browser
Go to: **http://localhost:3001**

### 2. Check Console (F12)
You should see:
```
🚀 Connecting to PLUTO backend...
🔌 Connecting to PLUTO backend...
✅ Connected to PLUTO backend
```

### 3. Test Command
Type in the command bar:
```
Open VS Code
```

**What should happen:**
1. Frontend sends command via WebSocket
2. Backend receives it
3. GPT-OSS processes the command
4. Backend executes `open_application` tool
5. VS Code launches
6. Activity logged in frontend
7. Success state shown

### 4. Test Voice Response
After a command completes, the backend can send voice responses via ElevenLabs.

---

## 📊 Check Backend Status

### Health Check
```bash
curl http://127.0.0.1:8765/health
```

Expected:
```json
{
  "status": "healthy",
  "agent": "PLUTO",
  "backend": "FastAPI",
  "environment": "development"
}
```

### System Metrics
```bash
curl http://127.0.0.1:8765/api/system/metrics
```

Expected:
```json
{
  "cpu": 34,
  "ram": 62,
  "storage": 71,
  "gpu": null,
  ...
}
```

### API Documentation
Visit: **http://127.0.0.1:8765/docs**

---

## 💬 Example Commands to Try

```
"Open VS Code"
→ Launches Visual Studio Code

"Create a folder called test in my Projects"
→ Creates ~/Projects/test

"What's my CPU usage?"
→ Shows system metrics

"Open YouTube"
→ Opens YouTube in browser

"Show me running processes"
→ Lists top processes

"Create a file called hello.txt"
→ Creates file in allowed directory
```

---

## 🐛 Troubleshooting

### Backend won't start

**Check Python version:**
```bash
python3 --version  # Need 3.12+
```

**Install dependencies:**
```bash
cd pluto-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend not connecting

**Check backend is running:**
```bash
curl http://127.0.0.1:8765/health
```

**Check browser console:**
- Open DevTools (F12)
- Look for WebSocket connection messages
- Should see "✅ Connected to PLUTO backend"

**If you see errors:**
```
❌ WebSocket error
⚠️ Cannot connect to PLUTO backend
```

Make sure:
1. Backend is running on port 8765
2. No firewall blocking the connection
3. CORS is configured (already set in .env)

### No voice output

**Check:**
1. ElevenLabs API key is correct in `.env`
2. Backend logs show TTS requests
3. Browser has audio permissions
4. Audio is not muted

**Test voice manually:**
```bash
curl -X POST http://127.0.0.1:8765/api/voice/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, I am PLUTO"}' \
  --output test.mp3

# Play the file
mpg123 test.mp3  # or any audio player
```

### Commands not executing

**Backend logs:**
```bash
# Terminal 1 (where backend is running)
# Watch for error messages
```

**Check allowed paths:**
```bash
cat pluto-backend/.env | grep PLUTO_ALLOWED_PATHS
```

Make sure target directory is in allowed paths!

**Check tool permissions:**
- Some operations require confirmation
- Look for action preview dialogs in UI

---

## 📁 Project Structure

```
pluto/
├── src/                        # Frontend (Next.js)
│   ├── app/page.tsx           # ✅ Updated with WebSocket
│   ├── services/
│   │   ├── ai.ts              # ✅ Real backend connection
│   │   ├── system.ts          # ✅ Real metrics from backend
│   │   └── voice.ts           # ✅ ElevenLabs TTS
│
├── pluto-backend/              # Backend (Python)
│   ├── app/
│   │   ├── main.py            # FastAPI app
│   │   ├── agent/             # Orchestrator & tools
│   │   ├── llm/               # GPT-OSS client
│   │   └── voice/             # ElevenLabs client
│   ├── .env                   # ✅ API keys configured
│   └── start.sh               # One-command startup
```

---

## 🎯 What's Working Now

✅ **WebSocket Connection** - Real-time frontend ↔ backend  
✅ **GPT-OSS Integration** - Llama 3.3 70B processes commands  
✅ **Tool Execution** - File operations, app launching, etc.  
✅ **Real System Metrics** - CPU, RAM from psutil  
✅ **ElevenLabs Voice** - Text-to-speech with Indian girl voice  
✅ **State Management** - Frontend shows agent states  
✅ **Activity Logging** - Actions recorded in timeline  
✅ **Security** - Path validation, command classification  

---

## 🎓 How It Works

```
User types command in frontend
         ↓
Frontend sends via WebSocket (ws://127.0.0.1:8765/api/chat/ws)
         ↓
Backend receives command
         ↓
Agent Orchestrator analyzes with GPT-OSS
         ↓
GPT-OSS decides which tool to use
         ↓
Backend executes tool (with security checks)
         ↓
Result sent back to frontend via WebSocket events
         ↓
Frontend updates UI (state, activity, etc.)
         ↓
Optional: ElevenLabs synthesizes voice response
```

---

## 📚 Next Steps

1. ✅ Backend and frontend running
2. ✅ WebSocket connected
3. 🧪 Try commands and verify they work
4. 🎨 Adjust UI based on responses
5. 🔊 Test voice synthesis
6. 🚀 Add more tools as needed

---

## 🆘 Need Help?

- **Backend Logs:** Check Terminal 1
- **Frontend Console:** Press F12 in browser
- **API Docs:** http://127.0.0.1:8765/docs
- **Test Backend:** `python pluto-backend/test_backend.py`

---

**Your PLUTO AI Assistant is now connected and ready! 🎉**

Start typing commands and watch the magic happen! ✨
