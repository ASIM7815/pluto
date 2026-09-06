# PLUTO Level 1 - Quick Start Guide 🚀

## Prerequisites

### 1. Install System Dependencies
```bash
sudo apt install wmctrl xdotool scrot xclip pulseaudio-utils
```

### 2. Verify Installation
```bash
which wmctrl xdotool scrot xclip pactl
# All commands should return paths
```

---

## Running the Backend

### 1. Activate Virtual Environment
```bash
cd pluto-backend
source venv/bin/activate
```

### 2. Start Backend Server
```bash
python -m app.main
```

Expected output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8765
```

---

## Running Tests

### Run Full Test Suite
```bash
cd pluto-backend
source venv/bin/activate
python test_level_1.py
```

### Expected Results
- ✅ 35-40 tests passed
- ⏭️ 0-5 tests skipped (if dependencies missing)
- ❌ 0 tests failed

---

## Testing API Endpoints

### 1. Get System Capabilities
```bash
curl http://localhost:8765/api/tools/capabilities
```

Expected response:
```json
{
  "level": 1,
  "features": [
    "Terminal-first desktop control",
    "Application management",
    "File operations",
    ...
  ],
  "continuous_listening": true,
  "context_awareness": true
}
```

### 2. List All Tools
```bash
curl http://localhost:8765/api/tools/v2/list
```

Expected: List of 15 tools with descriptions

### 3. Get System Status
```bash
curl http://localhost:8765/api/tools/status
```

Expected: Current state, tool count, uptime

### 4. Get Context Summary
```bash
curl http://localhost:8765/api/tools/context/summary
```

---

## Testing Voice Commands (Frontend Required)

### Basic Commands

#### Application Management
- **"Open Firefox"** → Launches Firefox browser
- **"Close Firefox"** → Closes Firefox
- **"Switch to VSCode"** → Focuses VSCode window
- **"List running applications"** → Shows all open apps

#### File Management
- **"Open Downloads folder"** → Opens ~/Downloads in file manager
- **"Find files named report"** → Searches for files
- **"Create folder Projects/test"** → Creates new directory

#### System Control
- **"Take a screenshot"** → Captures full screen
- **"Set volume to 50"** → Sets volume to 50%
- **"Get current volume"** → Tells you volume level
- **"Copy this text to clipboard"** → Copies text

### Context-Aware Multi-Step Commands

#### Example 1: YouTube Search
1. **"Open YouTube"**
   - Response: "Opened YouTube"
   - Context: browser_url = "https://youtube.com"

2. **"Search Iron Man"** (follow-up, no need to say "on YouTube")
   - Response: "Found Iron Man videos"
   - Context: search_query = "iron man", page_type = "search"

3. **"Play the second video"** (follow-up)
   - Response: "Playing Iron Man video"

#### Example 2: File Management
1. **"Open Documents folder"**
   - Context: current_directory = "~/Documents"

2. **"Find files named report"** (searches in Documents)
   - Response: Lists found files

3. **"Open the first one"** (context: knows the file list)
   - Opens first file from search results

---

## Troubleshooting

### Backend won't start
**Error:** `ModuleNotFoundError`
**Fix:** 
```bash
cd pluto-backend
pip install -r requirements.txt
```

### Tools not working
**Error:** "Command not found: wmctrl"
**Fix:** Install system dependencies
```bash
sudo apt install wmctrl xdotool scrot xclip pulseaudio-utils
```

### Voice not working
**Issue:** Backend started but voice commands don't work
**Check:**
1. Frontend is running on port 3001
2. WebSocket connection established
3. Microphone permissions granted in browser

### Context not working
**Issue:** Follow-up commands don't understand context
**Check:**
1. Backend logs show context updates
2. `/api/tools/context/summary` returns data
3. Commands are in same session (WebSocket not disconnected)

---

## Verifying Level 1 Implementation

### Checklist

✅ **Backend Running**
```bash
curl http://localhost:8765/health
# Should return: {"status": "healthy"}
```

✅ **15 Tools Available**
```bash
curl http://localhost:8765/api/tools/v2/list | grep -o '"name"' | wc -l
# Should return: 15
```

✅ **State Machine Working**
```bash
curl http://localhost:8765/api/tools/status
# Should show current state (idle/listening)
```

✅ **Context Manager Working**
```bash
curl http://localhost:8765/api/tools/context
# Should return empty context (before any commands)
```

✅ **Test Suite Passing**
```bash
python test_level_1.py
# Should show all tests passed
```

---

## Next Steps

### 1. Frontend Integration
- Start frontend on port 3001
- Connect WebSocket to backend
- Test voice input → command execution flow

### 2. Voice Testing
- Test single commands
- Test multi-step context-aware commands
- Test "silence" command

### 3. Real-World Usage
- Try daily tasks (open apps, manage files, control system)
- Observe context tracking in action
- Verify continuous listening loop

### 4. Level 2 Preparation
- Browser automation with Playwright
- More advanced context understanding
- Multi-app workflows

---

## Support & Documentation

- **Full Documentation:** See `LEVEL_1_COMPLETE.md`
- **Implementation Details:** See `IMPLEMENTATION_SUMMARY.md`
- **Implementation Spec:** See `LEVEL_1_IMPLEMENTATION.md`
- **Test Suite:** Run `python test_level_1.py`

---

## Quick Command Reference

### Backend Control
```bash
# Start backend
cd pluto-backend && source venv/bin/activate && python -m app.main

# Run tests
python test_level_1.py

# Check logs
tail -f pluto-backend/logs/pluto.log
```

### API Endpoints
```bash
# Health check
curl http://localhost:8765/health

# List tools
curl http://localhost:8765/api/tools/v2/list

# System status
curl http://localhost:8765/api/tools/status

# Capabilities
curl http://localhost:8765/api/tools/capabilities

# Context
curl http://localhost:8765/api/tools/context/summary
```

---

## Success Indicators

✅ Backend responds to health check  
✅ 15 tools listed in V2 registry  
✅ Test suite passes (35+ tests)  
✅ System dependencies installed  
✅ Voice commands execute successfully  
✅ Context tracking works across commands  
✅ Continuous listening loop functions  

**When all indicators are ✅, PLUTO Level 1 is fully operational! 🎉**
