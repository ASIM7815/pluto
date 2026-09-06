# 🚀 P L U T O — Complete AI Project Documentation

**A Futuristic Autonomous Linux Desktop AI Assistant**

*Next.js Frontend + FastAPI Backend + GPT-OSS 120B Brain + Python Control Layer + ElevenLabs Voice + Playwright Browser Automation*

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [What PLUTO Can Do](#what-pluto-can-do)
3. [System Architecture](#system-architecture)
4. [Complete Agent Workflow](#complete-agent-workflow)
5. [State Machine & Agent States](#state-machine--agent-states)
6. [Tool System (31 Tools)](#tool-system-31-tools)
7. [Context Management](#context-management)
8. [Voice Integration](#voice-integration)
9. [Security & Safety](#security--safety)
10. [Technology Stack](#technology-stack)
11. [Installation & Setup](#installation--setup)
12. [Usage Examples](#usage-examples)
13. [API Reference](#api-reference)
14. [File Structure](#file-structure)

---

## 🎯 Project Overview

**PLUTO** (Personal Linux Universal Task Orchestrator) is an **autonomous AI desktop assistant** that understands natural language voice/text commands and executes real tasks on your Linux computer. Unlike chatbots that only provide text responses, PLUTO can:

- **Control your desktop**: Open applications, manage windows, switch between apps
- **Automate your browser**: Navigate websites, search, click elements, fill forms
- **Manage files**: Create, read, move, copy, delete files and folders
- **Control your system**: Take screenshots, adjust volume, manage clipboard
- **Send messages**: Integrate with messaging platforms
- **Execute terminal commands**: Run system commands safely

PLUTO operates continuously in a **listening loop** — after completing one task, it immediately returns to LISTENING mode, ready for your next command. This creates a seamless, conversation-like experience.

---

## 🌟 What PLUTO Can Do

### 1️⃣ Application Management (4 Tools)
- **Open Applications**: "Open Firefox", "Launch VS Code", "Start Spotify"
- **Close Applications**: "Close Chrome", "Quit Slack"
- **Switch Applications**: "Switch to Terminal", "Focus on Firefox"
- **List Applications**: "What apps are running?"

### 2️⃣ Browser Automation (7 Tools)
- **Navigate URLs**: "Open YouTube", "Go to GitHub"
- **Search Websites**: "Search Iron Man on YouTube", "Google the weather"
- **Click Elements**: "Choose the second video", "Click the first link"
- **Type & Fill Forms**: "Type my email address"
- **Press Keys**: "Press Enter", "Press F for fullscreen"
- **Fullscreen Mode**: "Go fullscreen"
- **Page Snapshot**: "What's on this page?"

**Real Browser Control**: Uses Playwright to control a real Chromium browser with actual DOM interaction — not simulated!

### 3️⃣ File Management (10 Tools)
- **Open Files**: "Open document.pdf", "Open my photo"
- **Open Folders**: "Open Downloads folder"
- **Find Files**: "Find all Python files in projects"
- **Create Folders**: "Create a folder called work"
- **Create Files**: "Create a file notes.txt"
- **Read Files**: "Read the README file"
- **Move Files**: "Move report.pdf to Documents"
- **Copy Files**: "Copy config.json to backup"
- **Delete Files**: "Delete old_data.csv"
- **List Directory**: "What's in my home folder?"

### 4️⃣ System Control (7 Tools)
- **Screenshots**: "Take a screenshot", "Capture my screen"
- **Volume Control**: "Set volume to 50%", "What's the current volume?"
- **Clipboard**: "Copy this to clipboard", "What's in my clipboard?"
- **Process Management**: "List running processes", "Kill process 1234"
- **System Info**: "Show CPU usage", "Check memory"

### 5️⃣ Terminal Execution (1 Tool)
- **Execute Commands**: "Run npm install", "List files with ls -la"
- Safety-gated with confirmation for destructive commands

### 6️⃣ Messaging (2 Tools)
- **Send Messages**: "Send a message on Slack"
- **Open Chat Apps**: "Open WhatsApp Web"

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  Voice Input │  │  Text Input  │  │  Orb Visual  │            │
│  │  (Web Speech)│  │ (Command Bar)│  │  (States)    │            │
│  └──────┬───────┘  └──────┬───────┘  └──────▲───────┘            │
│         │                  │                  │                     │
│         └──────────────────┴──────────────────┘                     │
│                            │                                        │
└────────────────────────────┼────────────────────────────────────────┘
                             │
                    WebSocket Connection
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                      FASTAPI BACKEND                                │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   AGENT ORCHESTRATOR                         │  │
│  │  • Receives commands via WebSocket                          │  │
│  │  • Manages autonomous agent loop                            │  │
│  │  • Drives state machine transitions                         │  │
│  │  • Coordinates LLM, tools, and responses                    │  │
│  └──────┬────────────────────────────────────────────┬─────────┘  │
│         │                                            │             │
│  ┌──────▼──────────┐                        ┌───────▼──────────┐  │
│  │  STATE MACHINE  │                        │ CONTEXT MANAGER  │  │
│  │  12 States      │                        │  Session Memory  │  │
│  │  Transitions    │                        │  Current State   │  │
│  └─────────────────┘                        └──────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    GPT-OSS 120B (Groq)                       │  │
│  │  • Understands natural language intent                       │  │
│  │  • Plans tool execution strategy                             │  │
│  │  • Function-calling for tool selection                       │  │
│  │  • Observes results and reasons about next steps             │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐  │
│  │                     TOOL REGISTRY (31 Tools)                 │  │
│  │                                                              │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐           │  │
│  │  │Application │  │  Browser   │  │   File     │           │  │
│  │  │   Tools    │  │   Tools    │  │   Tools    │           │  │
│  │  │   (4)      │  │   (7)      │  │   (10)     │           │  │
│  │  └────────────┘  └────────────┘  └────────────┘           │  │
│  │                                                              │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐           │  │
│  │  │  System    │  │ Messaging  │  │ Terminal   │           │  │
│  │  │   Tools    │  │   Tools    │  │   Tools    │           │  │
│  │  │   (7)      │  │   (2)      │  │   (1)      │           │  │
│  │  └────────────┘  └────────────┘  └────────────┘           │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐  │
│  │                 EXECUTION LAYER                              │  │
│  │  • Playwright (Browser automation)                           │  │
│  │  • Subprocess (Terminal commands)                            │  │
│  │  • Filesystem APIs (File operations)                         │  │
│  │  • System APIs (Volume, screenshots, clipboard)              │  │
│  │  • Process management (psutil)                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              VOICE & SPEECH (ElevenLabs)                     │  │
│  │  • Text-to-Speech: Converts responses to natural voice       │  │
│  │  • Fallback to browser TTS if no API key                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     LINUX OPERATING SYSTEM                          │
│  • Desktop applications (Firefox, VS Code, Spotify, etc.)           │
│  • Filesystem (/home, /tmp, allowed paths)                          │
│  • System resources (Audio, Display, Processes)                     │
│  • Chromium browser (managed by Playwright)                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Complete Agent Workflow

### The Autonomous Agent Loop

PLUTO operates in a continuous **Listen → Understand → Plan → Act → Observe → Reason → Speak → Listen** loop:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PLUTO AGENT LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────────┘

1. IDLE / LISTENING
   │  • Red orb pulses, ready for input
   │  • Microphone active (Web Speech API)
   │  • WebSocket connected to backend
   │
   └─► User speaks: "Open YouTube and search Iron Man"

2. UNDERSTANDING
   │  • Command sent to backend via WebSocket
   │  • Text preprocessed and normalized
   │  • Session context retrieved (previous commands, current state)
   │
   └─► Command understood: "Open YouTube + Search on YouTube"

3. THINKING
   │  • GPT-OSS 120B receives the command
   │  • Context injected: "Current browser: None, Last search: None"
   │  • AI analyzes user intent
   │  • Determines required actions
   │
   └─► Decision: "Need to use open_url tool, then browser_search tool"

4. PLANNING
   │  • AI generates function call plan
   │  • Tool: open_url, Parameters: {url: "https://www.youtube.com"}
   │  • Safety check: SAFE (no confirmation needed)
   │  • Execution strategy determined
   │
   └─► Plan: "First open YouTube, then search for 'Iron Man'"

5. EXECUTING
   │  • Tool Registry executes: open_url("https://www.youtube.com")
   │  • Browser Manager checks if browser is alive
   │  • Launches Chromium with Playwright
   │  • Navigates to YouTube
   │  • Waits for page load (domcontentloaded)
   │
   └─► Result: Success, page loaded, title "YouTube"

6. VERIFYING
   │  • Tool result checked: success=True
   │  • Context updated: current_url="https://www.youtube.com"
   │  • Page title verified: "YouTube"
   │  • State confirmed: Browser ready for next action
   │
   └─► Verification: ✓ Page loaded successfully

7. OBSERVING
   │  • Tool result observed by AI
   │  • Current state: "Browser open, YouTube loaded"
   │  • Context: "User asked for search, need browser_search next"
   │
   └─► Observation: "YouTube is ready, proceed with search"

8. REASONING
   │  • AI evaluates: "First step done, need second step"
   │  • Decision: Continue with browser_search tool
   │  • Parameters: {query: "Iron Man", site: "youtube"}
   │
   └─► Reasoning: "Execute browser_search on YouTube"

9. EXECUTING (Step 2)
   │  • Tool: browser_search(query="Iron Man", site="youtube")
   │  • Constructs search URL: youtube.com/results?search_query=Iron+Man
   │  • Navigates to search results page
   │  • Waits for results to load
   │
   └─► Result: Success, search results displayed

10. VERIFYING (Step 2)
    │  • Context updated: last_search_query="Iron Man"
    │  • Page type: "youtube_search"
    │  • Results available for clicking (indexed)
    │
    └─► Verification: ✓ Search completed

11. SPEAKING
    │  • GPT-OSS generates response: "I've opened YouTube and searched for Iron Man"
    │  • Text sent to ElevenLabs TTS API
    │  • Audio streamed back to frontend
    │  • Orb visualizes speaking state
    │  • Audio played through speakers
    │
    └─► Speech: "I've opened YouTube and searched for Iron Man"

12. SUCCESS → LISTENING
    │  • Task marked complete
    │  • State machine: SUCCESS → LISTENING
    │  • Orb returns to red pulsing state
    │  • Context preserved (YouTube open, search done)
    │  • Ready for follow-up command
    │
    └─► Ready for next command: "Choose the second video"

┌─────────────────────────────────────────────────────────────────────┐
│                     CONTINUOUS OPERATION                            │
│  • No reset between commands                                        │
│  • Context carries forward (browser stays open)                     │
│  • Follow-up commands use existing state                            │
│  • Natural conversation flow maintained                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Multi-Step Task Example

**User Command Chain:**
1. "Open YouTube" 
2. "Search Iron Man"
3. "Choose the second video"
4. "Go fullscreen"

**PLUTO's Execution:**
```
Step 1: open_url("https://www.youtube.com")
  ↓ Context: current_url = "youtube.com", browser ready
  
Step 2: browser_search(query="Iron Man", site="youtube")
  ↓ Context: last_search_query = "Iron Man", results available
  
Step 3: browser_click(selector="a#video-title", index=1)  # 0-indexed
  ↓ Context: selected_result_index = 1, video playing
  
Step 4: browser_key(key="f11")  # Fullscreen toggle
  ↓ Context: fullscreen = true, video playing fullscreen
```

Each step:
- Uses context from previous steps
- Updates context for next steps
- Verifies successful execution
- Returns to LISTENING for next command

---

## 🎛️ State Machine & Agent States

PLUTO's behavior is governed by a **12-state finite state machine** that tracks the current phase of command execution:

### State Definitions

| State | Description | Orb Color | Transitions To |
|-------|-------------|-----------|----------------|
| **IDLE** | No active session, ready to start | Gray | LISTENING |
| **LISTENING** | Actively waiting for voice/text input | Red (pulsing) | UNDERSTANDING |
| **UNDERSTANDING** | Processing and parsing the command | Orange | THINKING |
| **THINKING** | AI analyzing intent and context | Yellow | PLANNING |
| **PLANNING** | Determining tool execution strategy | Blue | EXECUTING |
| **EXECUTING** | Running a tool/action | Purple | VERIFYING |
| **VERIFYING** | Checking if action succeeded | Cyan | OBSERVING, ERROR |
| **OBSERVING** | Reading tool result/observation | Teal | REASONING |
| **REASONING** | Deciding next step from observation | Magenta | THINKING, SPEAKING |
| **SPEAKING** | Generating and playing voice response | Green | SUCCESS |
| **SUCCESS** | Task completed successfully | Bright Green | LISTENING |
| **ERROR** | Task failed or was interrupted | Red (solid) | LISTENING, IDLE |

### State Transitions

**Valid Transitions** (enforced by StateMachine):
```python
IDLE → LISTENING → UNDERSTANDING → THINKING → PLANNING 
→ EXECUTING → VERIFYING → OBSERVING → REASONING 
→ THINKING (multi-step) | SPEAKING → SUCCESS → LISTENING
                                              ↑
                                          ERROR → LISTENING
```

### State Machine Features

1. **Strict Validation**: Invalid transitions are blocked and logged
2. **Force Transitions**: Error recovery can force transitions when needed
3. **History Tracking**: All transitions logged with timestamps and reasons
4. **Busy Detection**: `is_busy()` returns true for working states
5. **Ready Detection**: `is_ready_for_command()` checks if can accept new input
6. **Async Listeners**: Components can subscribe to state changes

### Implementation (`app/agent/state_machine.py`)

```python
class StateMachine:
    def transition(self, new_state: PlutoState, reason: str, force: bool = False):
        """Synchronous state transition"""
        if not force and not self.can_transition(new_state):
            return False
        # Perform transition, log, notify listeners
        
    async def transition_to(self, new_state: PlutoState, ...):
        """Async state transition with async listeners"""
        
    def is_busy(self) -> bool:
        """True if agent is working on a task"""
        return self.current_state in BUSY_STATES
        
    def is_ready_for_command(self) -> bool:
        """True if can accept new command"""
        return self.current_state in (IDLE, LISTENING, SUCCESS, ERROR)
```

---

## 🛠️ Tool System (31 Tools)

PLUTO's capabilities come from **31 specialized tools** organized into **6 categories**. Each tool is a Python class implementing the `TerminalTool` interface.

### Tool Registry Architecture

```python
class ToolRegistry:
    """Central registry managing all tools"""
    
    def __init__(self):
        self.tools: Dict[str, TerminalTool] = {}
        self.tools_by_category: Dict[str, List[str]] = {}
        
    def get_tool_schemas(self) -> List[Dict]:
        """OpenAI function-calling schemas for GPT"""
        
    def execute_tool(self, name: str, params: Dict) -> ToolResult:
        """Execute a tool and return result"""
        
    def verify_tool_result(self, result: ToolResult) -> bool:
        """Post-execution verification"""
```

### Tool Categories & Details

#### 1. Application Tools (4)

**`open_application`**
- Description: Launch a desktop application
- Parameters: `name` (app name: firefox, code, spotify, etc.)
- Safety: SAFE
- Example: `{"name": "firefox"}`
- Verification: Checks process list for running app

**`close_application`**
- Description: Close a running application
- Parameters: `name`, `force` (optional)
- Safety: CONFIRM (requires user approval)
- Example: `{"name": "spotify", "force": false}`
- Verification: Confirms process terminated

**`switch_to_application`**
- Description: Bring app window to foreground
- Parameters: `name`
- Safety: SAFE
- Example: `{"name": "code"}`
- Uses: `wmctrl -a` or `xdotool`

**`list_running_applications`**
- Description: List GUI applications currently running
- Parameters: None
- Safety: SAFE
- Returns: List of running app names

#### 2. Browser Tools (7)

**`open_url`**
- Description: Navigate browser to URL
- Parameters: `url`
- Safety: SAFE
- Example: `{"url": "https://youtube.com"}`
- Uses: Playwright browser.goto()

**`browser_search`**
- Description: Search on a specific site
- Parameters: `query`, `site` (default: "google")
- Safety: SAFE
- Supported sites: youtube, google, duckduckgo, bing, wikipedia, reddit, github, amazon, maps
- Example: `{"query": "Iron Man", "site": "youtube"}`

**`browser_click`**
- Description: Click an element on current page
- Parameters: `selector` (CSS), `index` (0-based), `text` (optional)
- Safety: SAFE
- Example: `{"selector": "a#video-title", "index": 1}`
- Uses: Playwright locator.click()

**`browser_key`**
- Description: Press a keyboard key in browser
- Parameters: `key` (Enter, Tab, Escape, f, F11, Space, etc.)
- Safety: SAFE
- Example: `{"key": "Enter"}`

**`browser_type`**
- Description: Type text into focused element
- Parameters: `text`
- Safety: SAFE
- Example: `{"text": "Hello World"}`

**`browser_fullscreen`**
- Description: Toggle browser fullscreen mode
- Parameters: None
- Safety: SAFE
- Uses: F11 key press

**`browser_snapshot`**
- Description: Capture current page state
- Parameters: `limit` (max elements, default: 40)
- Safety: SAFE
- Returns: Page title, URL, clickable elements list

#### 3. File Tools (10)

**`create_file`**
- Description: Create a new file
- Parameters: `path`, `content` (optional)
- Safety: SAFE
- Sandboxed to allowed paths

**`read_file`**
- Description: Read file contents
- Parameters: `path`, `lines` (optional)
- Safety: SAFE
- Returns: File content as text

**`open_file`**
- Description: Open file with default application
- Parameters: `path`
- Safety: SAFE
- Uses: `xdg-open`

**`open_folder`**
- Description: Open folder in file manager
- Parameters: `path`
- Safety: SAFE
- Uses: `nautilus`, `dolphin`, `thunar`, or `xdg-open`

**`list_directory`**
- Description: List directory contents
- Parameters: `path`, `recursive` (optional)
- Safety: SAFE
- Returns: List of files/folders

**`find_files`**
- Description: Search for files by pattern
- Parameters: `pattern`, `path` (optional)
- Safety: SAFE
- Uses: `find` command with pattern matching

**`create_folder`**
- Description: Create new directory
- Parameters: `path`
- Safety: SAFE
- Uses: `mkdir -p`

**`move_file`**
- Description: Move/rename file or folder
- Parameters: `source`, `destination`
- Safety: CONFIRM
- Uses: `mv` command

**`copy_file`**
- Description: Copy file or folder
- Parameters: `source`, `destination`
- Safety: SAFE
- Uses: `cp -r` command

**`delete_file`**
- Description: Delete file or folder
- Parameters: `path`, `recursive` (optional)
- Safety: CONFIRM
- Uses: `rm -rf` with confirmation

#### 4. System Tools (7)

**`take_screenshot`**
- Description: Capture screen screenshot
- Parameters: `path` (optional), `mode` (full/select/window)
- Safety: SAFE
- Uses: `scrot` command
- Returns: Screenshot file path

**`set_volume`**
- Description: Set system volume level
- Parameters: `level` (0-100)
- Safety: SAFE
- Uses: `pactl` (PulseAudio)

**`get_volume`**
- Description: Get current volume level
- Parameters: None
- Safety: SAFE
- Returns: Volume percentage

**`copy_to_clipboard`**
- Description: Copy text to clipboard
- Parameters: `text`
- Safety: SAFE
- Uses: `xclip` command

**`get_clipboard`**
- Description: Get clipboard contents
- Parameters: None
- Safety: SAFE
- Returns: Clipboard text

**`get_processes`**
- Description: List running system processes
- Parameters: `filter` (optional)
- Safety: SAFE
- Uses: `psutil`

**`kill_process`**
- Description: Terminate a process
- Parameters: `pid`, `force` (optional)
- Safety: CONFIRM
- Uses: `psutil.Process.terminate()`

#### 5. Messaging Tools (2)

**`send_message`**
- Description: Send message via configured platform
- Parameters: `message`, `recipient` (optional)
- Safety: CONFIRM
- Integration: Slack, Discord, etc.

**`open_chat_app`**
- Description: Open messaging application
- Parameters: `app` (slack, discord, whatsapp-web)
- Safety: SAFE
- Uses: Browser or native app

#### 6. Terminal Tools (1)

**`execute_command`**
- Description: Execute shell command
- Parameters: `command`
- Safety: CONFIRM (for dangerous commands), BLOCKED (for forbidden commands)
- Validation: Command safety classification
- Sandboxed execution with timeout

### Tool Result Structure

```python
@dataclass
class ToolResult:
    tool_name: str
    success: bool
    message: str
    output: Optional[str] = None
    error_code: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    verification_passed: bool = True
    context_updates: Optional[Dict[str, Any]] = None
```

### Safety Levels

```python
class SafetyLevel(Enum):
    SAFE = "safe"              # Execute immediately
    CONFIRM = "confirm"        # Requires user confirmation
    BLOCKED = "blocked"        # Never execute
```

---

## 🧠 Context Management

PLUTO maintains **persistent session context** that carries forward across commands, enabling natural follow-up interactions.

### SessionContext Structure

```python
@dataclass
class SessionContext:
    session_id: str
    
    # Application State
    current_app: Optional[str]
    running_apps: List[str]
    active_window: Optional[str]
    
    # Browser State
    current_browser: Optional[str]  # "chromium"
    current_url: Optional[str]      # "https://youtube.com/..."
    current_page_title: Optional[str]  # "Iron Man - YouTube"
    current_page_type: Optional[str]   # "youtube_search"
    visible_elements: List[Dict]    # Clickable elements
    
    # Search Context
    last_search_query: Optional[str]  # "Iron Man"
    search_results: List[Dict]
    selected_result_index: Optional[int]  # 1 (second video)
    
    # File Context
    current_directory: Optional[str]  # "/home/user/projects"
    recent_files: List[str]
    
    # Task Context
    previous_command: Optional[str]  # "Search Iron Man"
    current_task: Optional[str]
    task_steps_completed: int
    recent_actions: List[Action]  # Last 12 actions
    
    # Timestamps
    created_at: datetime
    last_activity: datetime
```

### Context Manager Features

**Context Lifecycle:**
```python
# Create session context
context = context_manager.create_context(session_id)

# Update context from tool results
context_manager.update_context(session_id, {
    "current_url": "https://youtube.com",
    "last_search_query": "Iron Man"
})

# Record action in history
context_manager.record_action(
    session_id,
    tool="browser_search",
    parameters={"query": "Iron Man"},
    result="Search completed",
    success=True
)

# Get context summary for LLM
summary = context_manager.get_context_summary(session_id)
# Returns: "Current URL: https://youtube.com | Last search: 'Iron Man' | Recent actions: browser_search"

# Expire old contexts
context_manager.cleanup_expired_contexts()
```

**Context-Aware Command Resolution:**

Without context:
- User: "Open YouTube" → PLUTO opens YouTube
- User: "Search Iron Man" → PLUTO doesn't know WHERE to search

With context:
- User: "Open YouTube" → PLUTO opens YouTube
  - Context: `current_url="https://youtube.com", current_browser="chromium"`
- User: "Search Iron Man" → PLUTO searches ON YouTube (not Google)
  - AI reads context: "User has YouTube open, search there"
  - Uses `browser_search(query="Iron Man", site="youtube")`

**Follow-up Command Examples:**

1. **Sequential Browser Actions:**
   ```
   "Open GitHub" → context: current_url = github.com
   "Search PLUTO" → browser_search on github
   "Open the first repository" → browser_click index=0
   ```

2. **File Operations:**
   ```
   "Open Downloads folder" → context: current_directory = /home/user/Downloads
   "Create a folder called work" → creates /home/user/Downloads/work
   "Move report.pdf there" → moves to /home/user/Downloads/work/
   ```

3. **Multi-Step Workflows:**
   ```
   "Open YouTube"
   "Search funny cats"
   "Choose the second video"
   "Go fullscreen"
   "Set volume to 70%"
   ```

---

## 🎤 Voice Integration

PLUTO supports **voice input** (Speech-to-Text) and **voice output** (Text-to-Speech) for hands-free operation.

### Speech-to-Text (STT)

**Implementation**: Web Speech API (browser-native)

```typescript
// services/voice.ts
const recognition = new webkitSpeechRecognition();
recognition.continuous = false;
recognition.lang = 'en-US';

recognition.onresult = (event) => {
  const transcript = event.results[0][0].transcript;
  // Send to backend for processing
  aiService.sendCommand(transcript);
};

recognition.start();
```

**Features:**
- Real-time speech recognition
- Noise cancellation
- Multiple language support
- Visual feedback (waveform animation)

### Text-to-Speech (TTS)

**Primary**: ElevenLabs API (high-quality neural TTS)
**Fallback**: Browser SpeechSynthesis API

```typescript
// services/tts.ts
export const playResponseSpeech = async (text: string) => {
  if (hasElevenLabsKey()) {
    // Use ElevenLabs for premium voice quality
    const audioBlob = await fetchElevenLabsTTS(text);
    playAudio(audioBlob);
  } else {
    // Fallback to browser TTS
    const utterance = new SpeechSynthesisUtterance(text);
    speechSynthesis.speak(utterance);
  }
};
```

**ElevenLabs Features:**
- Natural, human-like voice
- Emotional intonation
- Multiple voice choices
- Streaming audio playback

**Browser TTS Features:**
- Zero-cost fallback
- No API key required
- Works offline
- Multiple voices available

### Voice Modes

1. **Voice-Only Mode**: Hands-free operation
   - Hold spacebar or click mic to speak
   - Release to send command
   - Hear spoken response

2. **Text-Only Mode**: Type commands
   - Still get spoken responses
   - Useful in quiet environments

3. **Mixed Mode**: Switch between voice and text
   - Flexibility for different contexts

---

## 🔒 Security & Safety

PLUTO implements **multiple security layers** to protect your system:

### 1. Path Sandboxing

**Allowed Paths** (configurable in `.env`):
```python
PLUTO_ALLOWED_PATHS = [
    "/home/user",
    "/tmp",
    "/var/tmp"
]

BLOCKED_PATHS = [
    "/etc",
    "/sys",
    "/proc",
    "/boot",
    "/root",
    "/.ssh",
    "/.gnupg"
]
```

**Enforcement:**
- All file operations validated against allowed paths
- Path traversal attempts (../) blocked
- Symlink traversal checked
- Root directories protected

### 2. Command Safety Classification

Terminal commands classified into three categories:

**SAFE Commands** (execute immediately):
```python
SAFE_COMMANDS = [
    "ls", "pwd", "echo", "cat", "grep",
    "find", "which", "date", "whoami",
    "df", "du", "free", "uptime"
]
```

**CONFIRM Commands** (require user approval):
```python
CONFIRM_COMMANDS = [
    "rm", "mv", "cp", "chmod", "chown",
    "kill", "killall", "pkill", "reboot",
    "shutdown", "systemctl", "apt", "npm"
]
```

**BLOCKED Commands** (never execute):
```python
BLOCKED_COMMANDS = [
    "dd", "mkfs", "fdisk", "parted",
    "iptables", "ufw", "passwd", "sudo su",
    "init 0", "init 6", ": (){ :|:& };:"  # fork bomb
]
```

### 3. Tool Safety Levels

Each tool has a safety level:

```python
class SafetyLevel(Enum):
    SAFE = "safe"        # No confirmation needed
    CONFIRM = "confirm"  # Requires confirmation dialog
    BLOCKED = "blocked"  # Never allowed
```

**Confirmation Flow:**
```
User: "Delete all .log files"
  ↓
AI plans: delete_file(path="*.log")
  ↓
Safety check: CONFIRM required
  ↓
Frontend shows dialog: "Confirm deletion?"
  ↓
User clicks "Approve"
  ↓
Tool executes
```

### 4. API Key Protection

- Keys stored only in backend `.env` file
- Never sent to frontend
- Never logged in plain text
- Separate keys for LLM and TTS

### 5. Browser Isolation

- Playwright runs in isolated browser context
- Separate profile from user's main browser
- No access to stored passwords/cookies
- Auto-reopens if manually closed

### 6. Process Limits

- Command timeout: 30 seconds default
- Memory limits enforced
- CPU throttling available
- Subprocess sandboxing

---

## 💻 Technology Stack

### Frontend (Next.js + React + TypeScript)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | **Next.js 14** | React framework with SSR |
| Language | **TypeScript** | Type-safe JavaScript |
| Styling | **Tailwind CSS** | Utility-first CSS framework |
| UI Components | **Custom React** | Orb, HUD, command bar, cards |
| State Management | **Zustand** | Lightweight state management |
| WebSocket Client | **Native WebSocket API** | Real-time backend communication |
| Voice Input | **Web Speech API** | Browser-native STT |
| Voice Output | **ElevenLabs + Browser TTS** | High-quality speech synthesis |
| Animations | **Framer Motion** | Smooth animations |
| 3D Orb | **Three.js** | WebGL-based 3D rendering |

### Backend (Python + FastAPI)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | **FastAPI** | High-performance async Python framework |
| Language | **Python 3.11+** | Backend logic |
| WebSocket | **FastAPI WebSockets** | Real-time bidirectional communication |
| LLM | **GPT-OSS 120B (Groq)** | Natural language understanding |
| TTS | **ElevenLabs API** | Neural text-to-speech |
| Browser Automation | **Playwright** | Chromium control |
| System Interaction | **psutil** | Process and system monitoring |
| File Operations | **pathlib + os** | Filesystem management |
| Terminal Execution | **subprocess** | Shell command execution |
| Logging | **structlog** | Structured logging |
| Configuration | **Pydantic** | Type-safe settings |
| Validation | **Pydantic** | Request/response validation |

### Development Tools

| Tool | Purpose |
|------|---------|
| **npm/node** | Frontend package management |
| **pip/venv** | Backend package management |
| **Git** | Version control |
| **ESLint** | JavaScript/TypeScript linting |
| **Prettier** | Code formatting |
| **pytest** | Python testing |
| **uvicorn** | ASGI server |

### External Services

| Service | Purpose | Required |
|---------|---------|----------|
| **Groq API** | GPT-OSS 120B inference | Optional (has mock mode) |
| **ElevenLabs** | Premium TTS | Optional (has browser TTS fallback) |

---

## 📦 Installation & Setup

### Prerequisites

```bash
# System requirements
- Linux (Ubuntu/Debian recommended)
- Python 3.11+
- Node.js 18+
- Chromium/Google Chrome
- Audio output (speakers/headphones)
- Microphone (for voice input)

# System packages
sudo apt update
sudo apt install -y \
  python3 python3-pip python3-venv \
  nodejs npm \
  scrot xclip xdotool wmctrl \
  pulseaudio-utils
```

### Backend Setup

```bash
cd pluto-backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browser
python -m playwright install chromium

# Configure environment
cp .env.example .env
nano .env  # Add your API keys

# Environment variables:
GPT_OSS_API_KEY=your_groq_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here
PLUTO_BACKEND_HOST=127.0.0.1
PLUTO_BACKEND_PORT=8765
PLUTO_ENV=development
PLUTO_LLM_MOCK_MODE=false
PLUTO_TTS_MOCK_MODE=false
PLUTO_BROWSER_HEADLESS=false
PLUTO_ALLOWED_PATHS=/home/user,/tmp

# Start backend
./start.sh
# or
python -m app.main
```

Backend will start on `http://127.0.0.1:8765`

### Frontend Setup

```bash
# Install Node dependencies
npm install

# Start development server
npm run dev
```

Frontend will start on `http://localhost:3000`

### Verify Installation

1. Open `http://localhost:3000` in browser
2. Check backend connection (green "Online" indicator)
3. Try voice command: Click mic, say "Open YouTube"
4. Or type command: Type "list running applications" and press Enter

### Production Build

```bash
# Frontend
npm run build
npm start  # Runs on port 3000

# Backend
uvicorn app.main:app --host 0.0.0.0 --port 8765
```

---

## 📚 Usage Examples

### Basic Commands

**Application Control:**
```
"Open Firefox"
"Launch VS Code"
"Close Spotify"
"What applications are running?"
```

**Browser Automation:**
```
"Open YouTube"
"Go to GitHub"
"Search for funny cat videos"
"Click the first video"
"Press fullscreen"
```

**File Management:**
```
"Create a folder called projects"
"List files in Downloads"
"Open my document"
"Move report.pdf to Documents"
"Delete old_backup.zip"
```

**System Control:**
```
"Take a screenshot"
"Set volume to 50%"
"What's the current volume?"
"Copy 'Hello World' to clipboard"
```

### Advanced Multi-Step Workflows

**Research Workflow:**
```
1. "Open Firefox"
2. "Search for quantum computing research papers"
3. "Open the third result"
4. "Take a screenshot"
5. "Create a folder called quantum_research"
6. "Save the screenshot to that folder"
```

**YouTube Video Workflow:**
```
1. "Open YouTube"
2. "Search for Python tutorials"
3. "Choose the second video"
4. "Go fullscreen"
5. "Set volume to 70%"
```

**Project Setup Workflow:**
```
1. "Create a folder called my_app"
2. "Open that folder"
3. "Create a file called README.md"
4. "Create folders called src, tests, docs"
5. "Open VS Code"
```

### Context-Aware Commands

**Without specifying context:**
```
User: "Open GitHub"
PLUTO: Opens https://github.com

User: "Search for Python projects"
PLUTO: Searches "Python projects" on GitHub (because GitHub is already open)

User: "Open the first result"
PLUTO: Clicks the first repository link
```

**File context:**
```
User: "Open Downloads folder"
PLUTO: Opens /home/user/Downloads

User: "List everything here"
PLUTO: Lists contents of Downloads folder

User: "Create a backup folder"
PLUTO: Creates /home/user/Downloads/backup
```

---

## 🔌 API Reference

### WebSocket API

**Endpoint:** `ws://localhost:8765/api/chat/ws?session_id=<optional>`

**Client → Server Messages:**

```typescript
// Send command
{
  "type": "command",
  "command": "Open YouTube"
}

// Confirm action
{
  "type": "confirm"
}

// Reject action
{
  "type": "reject"
}

// Interrupt execution
{
  "type": "interrupt"
}

// Reset session
{
  "type": "reset",
  "clearHistory": true
}
```

**Server → Client Messages:**

```typescript
// Session established
{
  "type": "session",
  "session_id": "abc123",
  "state": "listening"
}

// State change
{
  "type": "agent_state",
  "state": "executing",
  "task": "Opening YouTube...",
  "session_id": "abc123"
}

// Execution step
{
  "type": "execution_step",
  "step": "Navigating to https://youtube.com",
  "tool": "open_url",
  "progress": 50
}

// Speech response
{
  "type": "speak",
  "text": "I've opened YouTube for you",
  "audio_url": "https://..."
}

// Action requires confirmation
{
  "type": "action_preview",
  "action": "delete_file",
  "description": "Delete important_file.pdf",
  "safety": "confirm"
}

// Error occurred
{
  "type": "error",
  "message": "Could not open file: Permission denied",
  "code": "PERMISSION_DENIED"
}
```

### REST API Endpoints

**System:**
```
GET  /health
GET  /api/system/metrics
GET  /api/system/capabilities
POST /api/system/shutdown
```

**Tools:**
```
GET  /api/tools/registry
GET  /api/tools/list?category=browser
GET  /api/tools/{tool_name}
POST /api/tools/execute
POST /api/tools/verify
```

**Context:**
```
GET  /api/tools/context?session_id=abc123
GET  /api/tools/context/summary?session_id=abc123
POST /api/tools/context/update
POST /api/tools/context/reset
```

**Voice:**
```
POST /api/voice/transcribe
POST /api/voice/synthesize
GET  /api/voice/status
```

**Example: Execute Tool:**
```bash
curl -X POST http://localhost:8765/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "open_url",
    "parameters": {"url": "https://youtube.com"},
    "session_id": "test123"
  }'

# Response:
{
  "success": true,
  "message": "Loaded https://www.youtube.com/",
  "tool_name": "open_url",
  "data": {
    "url": "https://www.youtube.com/",
    "title": "YouTube"
  },
  "context_updates": {
    "current_url": "https://www.youtube.com/",
    "current_page_title": "YouTube",
    "current_browser": "chromium"
  }
}
```

---

## 📂 File Structure

```
pluto/
├── src/                              # Next.js Frontend
│   ├── app/                          # Next.js 14 app directory
│   │   ├── page.tsx                  # Home page (main UI)
│   │   ├── layout.tsx                # Root layout
│   │   ├── globals.css               # Global styles
│   │   ├── chat/                     # Chat page
│   │   ├── apps/                     # Apps page
│   │   ├── files/                    # Files page
│   │   ├── automations/              # Automations page
│   │   ├── system/                   # System page
│   │   └── settings/                 # Settings page
│   ├── components/                   # React components
│   │   ├── orb/                      # 3D Orb visualization
│   │   │   ├── PlutoOrb.tsx          # Main orb component
│   │   │   └── OrbStateLabels.tsx    # State indicators
│   │   ├── command/                  # Command input
│   │   │   ├── CommandBar.tsx        # Text/voice input
│   │   │   ├── VoiceButton.tsx       # Mic control
│   │   │   ├── VoiceWaveform.tsx     # Audio visualization
│   │   │   └── ExecutionPanel.tsx    # Step-by-step execution
│   │   ├── layout/                   # Layout components
│   │   │   ├── AppShell.tsx          # Main app shell
│   │   │   ├── Sidebar.tsx           # Navigation sidebar
│   │   │   ├── TopBar.tsx            # Top navigation
│   │   │   └── WindowControls.tsx    # Window controls
│   │   ├── activity/                 # Activity tracking
│   │   │   ├── ActivityPanel.tsx     # Activity feed
│   │   │   ├── ActivityTimeline.tsx  # Timeline view
│   │   │   └── ActivityItem.tsx      # Single activity
│   │   ├── cards/                    # UI cards
│   │   │   ├── GlassCard.tsx         # Glass morphism card
│   │   │   ├── ProductivityCard.tsx  # Productivity metrics
│   │   │   ├── ActionPreviewCard.tsx # Action confirmation
│   │   │   ├── ErrorCard.tsx         # Error display
│   │   │   └── ConfirmationDialog.tsx # Confirmation modal
│   │   ├── actions/                  # Quick actions
│   │   │   ├── QuickActions.tsx      # Action grid
│   │   │   └── QuickAction.tsx       # Single action
│   │   ├── system/                   # System info
│   │   │   ├── SystemOverview.tsx    # System metrics
│   │   │   └── MetricRing.tsx        # Circular metric
│   │   └── common/                   # Common components
│   │       ├── GlowButton.tsx        # Glowing button
│   │       ├── IconButton.tsx        # Icon button
│   │       └── StatusIndicator.tsx   # Status dot
│   ├── services/                     # Frontend services
│   │   ├── ai.ts                     # WebSocket AI service
│   │   ├── voice.ts                  # Voice input/output
│   │   ├── tts.ts                    # Text-to-speech
│   │   ├── system.ts                 # System metrics
│   │   └── tauri.ts                  # Tauri integration (future)
│   ├── hooks/                        # React hooks
│   │   ├── usePlutoState.ts          # PLUTO state management
│   │   ├── useSystemStats.ts         # System statistics
│   │   └── useVoice.ts               # Voice control
│   ├── store/                        # State management
│   │   └── plutoStore.ts             # Zustand store
│   ├── types/                        # TypeScript types
│   │   └── index.ts                  # Type definitions
│   └── lib/                          # Utilities
│       └── utils.ts                  # Helper functions
│
├── pluto-backend/                    # Python FastAPI Backend
│   ├── app/
│   │   ├── main.py                   # FastAPI application entry
│   │   ├── agent/                    # Agent system
│   │   │   ├── orchestrator.py       # Agent orchestrator (main loop)
│   │   │   ├── state_machine.py      # State machine (12 states)
│   │   │   ├── context_manager.py    # Session context manager
│   │   │   └── session_manager.py    # WebSocket session manager
│   │   ├── tools/                    # Tool implementations
│   │   │   ├── registry.py           # Tool registry (31 tools)
│   │   │   ├── terminal_base.py      # Base tool classes
│   │   │   ├── application_tools.py  # Application control (4)
│   │   │   ├── browser.py            # Browser automation (7)
│   │   │   ├── file_tools.py         # File operations (10)
│   │   │   ├── system_tools.py       # System control (7)
│   │   │   ├── messaging.py          # Messaging (2)
│   │   │   └── terminal.py           # Terminal execution (1)
│   │   ├── llm/                      # LLM integration
│   │   │   ├── gpt_oss.py            # GPT-OSS client (Groq)
│   │   │   └── mock_planner.py       # Mock LLM for testing
│   │   ├── voice/                    # Voice services
│   │   │   ├── elevenlabs.py         # ElevenLabs TTS
│   │   │   └── mock_tts.py           # Mock TTS
│   │   ├── api/                      # API routes
│   │   │   ├── routes_chat.py        # Chat WebSocket endpoint
│   │   │   ├── routes_voice.py       # Voice endpoints
│   │   │   ├── routes_system.py      # System endpoints
│   │   │   └── routes_tools.py       # Tool endpoints
│   │   ├── core/                     # Core utilities
│   │   │   ├── config.py             # Configuration (Pydantic)
│   │   │   ├── security.py           # Security validation
│   │   │   └── logging.py            # Structured logging
│   │   └── schemas/                  # Pydantic models
│   │       ├── chat.py               # Chat message schemas
│   │       ├── tools.py              # Tool schemas
│   │       └── system.py             # System schemas
│   ├── requirements.txt              # Python dependencies
│   ├── .env.example                  # Environment template
│   ├── .env                          # Environment config (gitignored)
│   └── start.sh                      # Backend startup script
│
├── public/                           # Static assets
│   ├── file.svg
│   ├── globe.svg
│   ├── next.svg
│   ├── vercel.svg
│   └── window.svg
│
├── Documentation/                    # Project documentation
│   ├── README.md                     # Main README
│   ├── ARCHITECTURE.md               # System architecture
│   ├── QUICK_START.md                # Quick start guide
│   ├── INTEGRATION_GUIDE.md          # Integration guide
│   ├── BACKEND_COMPLETE.md           # Backend documentation
│   ├── LEVEL_1_COMPLETE.md           # Level 1 features
│   ├── DEPLOYMENT_NOTES.md           # Deployment guide
│   └── PLUTO_COMPLETE_PROJECT_DOCUMENTATION.md  # This file
│
├── Configuration/                    # Configuration files
│   ├── package.json                  # Node dependencies
│   ├── package-lock.json             # Lockfile
│   ├── tsconfig.json                 # TypeScript config
│   ├── next.config.ts                # Next.js config
│   ├── postcss.config.mjs            # PostCSS config
│   ├── eslint.config.mjs             # ESLint config
│   └── .gitignore                    # Git ignore rules
│
└── Scripts/
    └── test_voice.sh                 # Voice testing script
```

---

## 🎓 Key Concepts Summary

### 1. Autonomous Operation
PLUTO doesn't just respond — it **acts autonomously**:
- Plans multi-step tasks
- Executes tools in sequence
- Verifies results
- Handles errors and retries
- Returns to listening automatically

### 2. Context Continuity
Every command builds on previous context:
- Browser stays open between commands
- Search results remembered for clicking
- File paths preserved for operations
- Task history maintained

### 3. Real Execution
All actions are real:
- Browser automation: actual Chromium with Playwright
- File operations: real filesystem changes
- System control: real volume/clipboard/screenshots
- Terminal commands: real subprocess execution

### 4. Safety First
Multiple security layers protect your system:
- Path sandboxing
- Command classification
- Confirmation dialogs
- Execution timeouts
- Process isolation

### 5. Natural Interaction
Voice + text + visual feedback create natural UX:
- Speak commands naturally
- See real-time state changes in orb
- Hear spoken responses
- View execution steps
- Get instant feedback

---

## 🚀 Future Enhancements

**Planned Features:**
- [ ] Multi-monitor support
- [ ] Calendar integration (Google Calendar, etc.)
- [ ] Email management (Gmail, Outlook)
- [ ] Code editor integration (VS Code API)
- [ ] Smart home control (Home Assistant)
- [ ] Task scheduling & automation
- [ ] Learning from user patterns
- [ ] Offline LLM mode (llama.cpp)
- [ ] Mobile app (React Native)
- [ ] Plugin system for custom tools

---

## 📞 Support & Contributing

**Issues:** Report bugs or request features on GitHub Issues

**Contributing:**
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Contact:** GitHub discussions for questions and ideas

---

## 📄 License

This project is licensed under the MIT License.

---

## 🙏 Acknowledgments

Built with:
- **Next.js** by Vercel
- **FastAPI** by Sebastián Ramírez
- **Playwright** by Microsoft
- **GPT-OSS (Groq)** for LLM inference
- **ElevenLabs** for neural TTS
- **Three.js** for 3D orb rendering
- **Tailwind CSS** for styling

---

**PLUTO** — Your Autonomous Linux Desktop AI Assistant 🚀

*Making desktop automation as natural as conversation.*
