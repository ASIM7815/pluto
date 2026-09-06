# PLUTO LEVEL 1: Autonomous Desktop Control - Implementation Plan

> **Goal**: Transform PLUTO from a chatbot into a voice-controlled autonomous computer assistant with continuous listening, context awareness, and verified action execution.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [State Machine](#state-machine)
4. [Tool System](#tool-system)
5. [Context Management](#context-management)
6. [Browser Automation](#browser-automation)
7. [Verification System](#verification-system)
8. [Continuous Listening](#continuous-listening)
9. [Implementation Phases](#implementation-phases)
10. [File Structure](#file-structure)
11. [Safety & Security](#safety-security)
12. [Testing Strategy](#testing-strategy)

---

## 🏗️ Architecture Overview

### Current State
```
Frontend (React/Next.js) → Backend (FastAPI) → GPT-OSS 120B → Tools → Response
                                              ↓
                                        ElevenLabs TTS
```

### Level 1 Target Architecture
```
Voice Input (Continuous)
    ↓
Speech Recognition (Python)
    ↓
Context Manager (Session State)
    ↓
GPT-OSS 120B (Intent & Planning)
    ↓
Tool Selector (Controlled Execution)
    ↓
Tool Execution (Desktop/Browser Actions)
    ↓
Verification System (Action Validation)
    ↓
ElevenLabs/gTTS Response
    ↓
Automatic Return to Listening ↻
```

### Communication Flow
```
Frontend ←→ WebSocket ←→ Python Backend
                            ↓
                    State Machine (IDLE → LISTENING → THINKING → 
                                   PLANNING → EXECUTING → VERIFYING → 
                                   SPEAKING → LISTENING)
                            ↓
                    Context Manager (Session Memory)
                            ↓
                    Tool Registry (Safe Actions)
                            ↓
                    Desktop/Browser Automation
```

---

## 🧩 Core Components

### 1. **Voice Pipeline Manager** (`app/voice/pipeline_manager.py`)

**Responsibilities:**
- Continuous speech recognition using `speech_recognition` library
- Voice Activity Detection (VAD) to detect when user is speaking
- Auto-start listening after TTS completes
- Wake word detection (optional: "Hey PLUTO")
- Noise filtering and silence detection

**Key Methods:**
```python
class VoicePipelineManager:
    async def start_listening(self) -> None
    async def stop_listening(self) -> None
    async def process_audio(self, audio_data) -> str
    async def on_speech_detected(self, text: str) -> None
    async def return_to_listening(self) -> None
```

**Dependencies:**
- `speech_recognition` - For STT
- `pyaudio` - Audio capture
- `webrtcvad` - Voice activity detection (optional)

---

### 2. **Context Manager** (`app/agent/context_manager.py`)

**Responsibilities:**
- Maintain session context across commands
- Track current application, browser, URL, page state
- Remember recent actions and their results
- Provide context to GPT-OSS for intent understanding
- Clear context when needed ("start fresh", timeout)

**Context Structure:**
```python
class SessionContext:
    session_id: str
    current_app: Optional[str]  # "firefox", "code", etc.
    current_browser_url: Optional[str]
    current_page_title: Optional[str]
    current_page_type: Optional[str]  # "youtube_search", "github_repo"
    visible_elements: List[Dict]  # Buttons, links, inputs on page
    recent_actions: List[Action]  # Last 5 actions
    search_query: Optional[str]
    search_results: List[Dict]
    previous_command: Optional[str]
    task_in_progress: Optional[str]
    created_at: datetime
    last_activity: datetime
```

**Key Methods:**
```python
class ContextManager:
    def get_context(self, session_id: str) -> SessionContext
    def update_context(self, session_id: str, updates: Dict)
    def add_action(self, session_id: str, action: Action)
    def clear_context(self, session_id: str)
    def get_context_summary(self, session_id: str) -> str
```

---

### 3. **State Machine** (`app/agent/state_machine.py`)

**States:**
```python
class PlutoState(Enum):
    IDLE = "idle"                    # Waiting for activation
    LISTENING = "listening"          # Recording voice input
    UNDERSTANDING = "understanding"  # Processing speech to text
    THINKING = "thinking"            # GPT-OSS analyzing intent
    PLANNING = "planning"            # Breaking down into steps
    EXECUTING = "executing"          # Running tool actions
    VERIFYING = "verifying"          # Checking if action succeeded
    SPEAKING = "speaking"            # TTS response
    ERROR = "error"                  # Something went wrong
```

**Transitions:**
```python
IDLE → LISTENING (voice detected or manual trigger)
LISTENING → UNDERSTANDING (speech ended)
UNDERSTANDING → THINKING (text extracted)
THINKING → PLANNING (intent identified)
PLANNING → EXECUTING (plan ready)
EXECUTING → VERIFYING (action completed)
VERIFYING → SPEAKING (result confirmed)
SPEAKING → LISTENING (response finished - AUTO)
ERROR → LISTENING (error explained)
```

**Implementation:**
```python
class StateMachine:
    def __init__(self):
        self.current_state = PlutoState.IDLE
        self.state_history = []
    
    async def transition_to(self, new_state: PlutoState, session: Session)
    async def emit_state_change(self, session: Session)
    def can_transition(self, from_state: PlutoState, to_state: PlutoState) -> bool
```

---

### 4. **Tool Registry v2** (`app/tools/registry_v2.py`)

**Enhanced Tool System:**

Each tool must have:
- **Name**: Unique identifier
- **Description**: What it does (for GPT-OSS)
- **Parameters**: Typed parameters with validation
- **Execution**: Actual implementation
- **Verification**: How to confirm success
- **Safety Level**: SAFE, CONFIRM_REQUIRED, DANGEROUS

**Tool Categories:**

#### A. Application Management
```python
- open_application(app_name: str) -> ToolResult
- close_application(app_name: str) -> ToolResult
- switch_to_application(app_name: str) -> ToolResult
- list_running_applications() -> ToolResult
- minimize_application(app_name: str) -> ToolResult
- maximize_application(app_name: str) -> ToolResult
```

#### B. Browser Control
```python
- open_url(url: str) -> ToolResult
- navigate_browser(url: str) -> ToolResult
- browser_back() -> ToolResult
- browser_forward() -> ToolResult
- browser_refresh() -> ToolResult
- browser_close_tab() -> ToolResult
- browser_new_tab() -> ToolResult
```

#### C. Browser Interaction (Playwright)
```python
- browser_click(selector: str) -> ToolResult
- browser_type(selector: str, text: str) -> ToolResult
- browser_search(query: str) -> ToolResult  # Smart search on current page
- browser_select_result(index: int) -> ToolResult
- browser_scroll(direction: str, amount: int) -> ToolResult
- browser_get_page_info() -> ToolResult
- browser_take_screenshot(path: str) -> ToolResult
```

#### D. File Management
```python
- open_file(path: str) -> ToolResult
- open_folder(path: str) -> ToolResult
- find_files(query: str, location: str) -> ToolResult
- create_folder(path: str) -> ToolResult
- rename_file(old_path: str, new_path: str) -> ToolResult
- move_file(source: str, destination: str) -> ToolResult
- copy_file(source: str, destination: str) -> ToolResult
```

#### E. System Control
```python
- take_screenshot(save_path: str) -> ToolResult
- set_volume(level: int) -> ToolResult
- get_system_info() -> ToolResult
- press_key(key: str) -> ToolResult
- type_text(text: str) -> ToolResult
- get_clipboard() -> ToolResult
- set_clipboard(text: str) -> ToolResult
```

#### F. Workspace Management
```python
- switch_workspace(workspace_id: int) -> ToolResult
- arrange_windows(layout: str) -> ToolResult  # "side-by-side", "stack"
- create_work_mode(apps: List[str]) -> ToolResult
```

**Tool Implementation Pattern:**
```python
class Tool:
    name: str
    description: str
    parameters: Dict[str, ParameterSpec]
    safety_level: SafetyLevel
    
    async def execute(self, **kwargs) -> ToolResult
    async def verify(self, result: ToolResult, **kwargs) -> bool
    async def rollback(self, **kwargs) -> None  # If possible
```

---

### 5. **Browser Automation Engine** (`app/automation/browser_engine.py`)

**Using Playwright for Universal Browser Control:**

```python
class BrowserEngine:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.page_analyzer = PageAnalyzer()
    
    async def initialize(self) -> None
    async def get_or_create_page(self) -> Page
    
    # Page Analysis
    async def get_page_info(self) -> PageInfo
    async def get_visible_elements(self) -> List[Element]
    async def identify_page_type(self) -> str  # "youtube_search", "google_results"
    
    # Smart Interaction
    async def smart_search(self, query: str) -> bool
    async def smart_select_result(self, index: int) -> bool
    async def wait_for_navigation(self, timeout: int = 10000) -> bool
    
    # Element Interaction
    async def click_element(self, selector: str) -> bool
    async def type_in_element(self, selector: str, text: str) -> bool
    async def scroll_page(self, direction: str, amount: int) -> bool
    
    # Verification
    async def verify_url(self, expected_url: str) -> bool
    async def verify_element_visible(self, selector: str) -> bool
    async def verify_page_loaded(self) -> bool
```

**Page Type Handlers:**

Each website type gets a handler:
```python
class YouTubeHandler(PageHandler):
    async def search(self, query: str) -> bool
    async def select_video(self, index: int) -> bool
    async def get_search_results(self) -> List[VideoResult]

class GoogleHandler(PageHandler):
    async def search(self, query: str) -> bool
    async def select_result(self, index: int) -> bool
    async def get_search_results(self) -> List[SearchResult]

class GitHubHandler(PageHandler):
    async def search_repos(self, query: str) -> bool
    async def open_repo(self, index: int) -> bool
```

---

### 6. **Verification System** (`app/verification/verifier.py`)

**Action Verification:**

```python
class ActionVerifier:
    async def verify_application_opened(self, app_name: str) -> bool
    async def verify_url_opened(self, url: str) -> bool
    async def verify_file_opened(self, file_path: str) -> bool
    async def verify_search_results(self, query: str) -> bool
    async def verify_element_clicked(self, selector: str) -> bool
    async def verify_window_switched(self, app_name: str) -> bool
```

**Verification Strategies:**

1. **Process Check**: Verify process is running
   ```python
   ps aux | grep firefox
   ```

2. **Window Title Check**: Verify window title changed
   ```python
   xdotool getwindowfocus getwindowname
   ```

3. **URL Check**: Verify browser URL matches expected
   ```python
   page.url == expected_url
   ```

4. **Element Check**: Verify element exists/visible
   ```python
   await page.is_visible(selector)
   ```

5. **Content Check**: Verify page content contains expected text
   ```python
   await page.inner_text(selector)
   ```

**Retry Logic:**
```python
class RetryPolicy:
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_on_errors: List[Exception]
    
    async def execute_with_retry(self, func, *args, **kwargs)
```

---

### 7. **Intent Understanding** (`app/agent/intent_parser.py`)

**Enhanced GPT-OSS Integration:**

**System Prompt Enhancement:**
```python
SYSTEM_PROMPT = """You are PLUTO, an autonomous desktop control AI.

Current Context:
- Current App: {current_app}
- Current Browser URL: {current_url}
- Current Page: {page_title}
- Recent Actions: {recent_actions}
- Available Elements: {visible_elements}

When the user gives a command, you must:
1. Understand their intent considering the current context
2. Choose the appropriate tool(s)
3. Provide clear parameters
4. Consider what verification is needed

If the command is ambiguous (like "choose the second one"), use the context 
to understand what "one" refers to. If context is insufficient, ask briefly.

Tools available:
{tool_descriptions}

Respond with a structured plan in JSON format.
"""
```

**Intent Response Format:**
```json
{
  "intent": "search_video",
  "confidence": 0.95,
  "requires_context": true,
  "steps": [
    {
      "tool": "browser_search",
      "parameters": {"query": "Iron Man"},
      "verification": "search_results_visible"
    }
  ],
  "clarification_needed": false,
  "natural_response": "Searching for Iron Man on YouTube."
}
```

---

### 8. **Orchestrator v2** (`app/agent/orchestrator_v2.py`)

**Main Control Loop:**

```python
class AutonomousOrchestrator:
    def __init__(self):
        self.state_machine = StateMachine()
        self.context_manager = ContextManager()
        self.tool_registry = ToolRegistryV2()
        self.voice_pipeline = VoicePipelineManager()
        self.browser_engine = BrowserEngine()
        self.verifier = ActionVerifier()
    
    async def start(self, session: Session):
        """Main autonomous loop"""
        
        # 1. Start continuous listening
        await self.voice_pipeline.start_listening()
        await self.state_machine.transition_to(PlutoState.LISTENING, session)
        
        while session.active:
            try:
                # 2. Wait for voice command
                command = await self.voice_pipeline.wait_for_command()
                
                # 3. Understanding
                await self.state_machine.transition_to(PlutoState.UNDERSTANDING, session)
                
                # 4. Thinking - Get context and plan
                await self.state_machine.transition_to(PlutoState.THINKING, session)
                context = self.context_manager.get_context(session.id)
                
                # 5. Planning - Use GPT-OSS with context
                await self.state_machine.transition_to(PlutoState.PLANNING, session)
                plan = await self.create_plan(command, context)
                
                # 6. Executing - Run tools
                await self.state_machine.transition_to(PlutoState.EXECUTING, session)
                results = []
                for step in plan.steps:
                    result = await self.execute_step(step, context)
                    results.append(result)
                    
                    # Update context after each step
                    self.context_manager.update_context(session.id, result.context_updates)
                
                # 7. Verifying - Check results
                await self.state_machine.transition_to(PlutoState.VERIFYING, session)
                verification = await self.verify_results(results, plan)
                
                # 8. Speaking - Generate response
                await self.state_machine.transition_to(PlutoState.SPEAKING, session)
                response_text = self.generate_response(verification, plan)
                await self.speak(response_text, session)
                
                # 9. Auto-return to listening
                await self.statUpgrade PLUTO to **Level 1 autonomous desktop control using Python**. The main goal is to make PLUTO capable of continuously listening to my voice, understanding what I want, performing the required action on my Linux computer, verifying that the action was actually completed, speaking the result through ElevenLabs, and then immediately listening for my next command. PLUTO should not behave like a normal chatbot on the Home screen. Home should function as the command and autonomous-control interface, while the Chat section can remain a normal conversational interface.

The basic flow should be: **Voice input → Speech recognition → GPT-OSS 120B understanding and planning → Python tool execution → Desktop or browser action → Verification → ElevenLabs voice response → Continuous listening.**

Build the autonomous logic primarily in Python and integrate it cleanly with the existing PLUTO React/Next.js frontend. Do not destroy the existing frontend or redesign it unnecessarily. Python should become the main orchestration layer responsible for listening, understanding the command, maintaining the current task context, selecting tools, executing actions, verifying results and communicating the current state back to the frontend. The frontend should visually show states such as idle, listening, thinking, planning, executing, verifying, speaking and error.

PLUTO must use the existing GPT-OSS 120B API as its reasoning and planning model. Do not allow the language model to directly execute arbitrary Linux shell commands. Instead, create a controlled Python tool system where the model chooses from predefined tools such as opening applications, opening URLs, opening files, opening folders, switching windows, taking screenshots, controlling volume, typing text, clicking browser elements, scrolling, searching websites and selecting browser results. Every tool should have a clear name, description, parameters, execution function and verification function. This will make PLUTO much safer and will also allow additional tools to be added later.

The most important requirement is **continuous listening**. After PLUTO completes one task, it must not stop the voice system and it must not require me to press the microphone button again. After speaking its response, PLUTO should automatically return to the listening state and wait for my next command. I should be able to have a natural sequence of commands without restarting the assistant after every action. PLUTO should maintain the current session context so that short follow-up commands such as "open this", "choose the second one", "click that", "scroll down", "go back" or "search for this" can be understood from what PLUTO is currently seeing and doing.

Use browser automation such as Playwright for browser interaction. PLUTO must be able to understand the current browser page instead of depending only on fixed screen coordinates. It should be able to identify the current URL, page title, visible text, input fields, buttons, links and relevant interactive elements. It should wait for pages to load, interact with the correct elements and verify that the expected result happened. Make the browser automation reusable so it works for many websites instead of hardcoding only YouTube.

For example, I should be able to say **"PLUTO, open YouTube."** PLUTO should open YouTube in the browser, verify that YouTube is actually open, speak something short such as **"YouTube is open, BOSS."**, and then automatically return to listening. Without pressing anything again, I should then be able to say **"Search Iron Man."** Because PLUTO knows that the current browser page is YouTube, it should understand that I want to search for Iron Man on YouTube. It should interact with the search field, perform the search, wait for the results and verify that the results are available. After completing the task, it should give a short voice response and return to listening again.

Then I should be able to say **"Choose the second video."** PLUTO must understand that I am referring to the current YouTube search results for Iron Man. It should identify the relevant visible video results, determine which one is the second result, select it and verify that the selected video page actually opened. PLUTO should then say something like **"Done, BOSS."** and immediately return to listening. This entire sequence must work as one continuous interaction rather than three unrelated chatbot conversations.

Do not implement this by hardcoding specific phrases such as "open YouTube", "search Iron Man" or "choose second video". Those are only examples for testing the system. Build a general-purpose intent and tool architecture so that the same system can understand commands such as opening GitHub, searching something on a website, selecting the first result, opening a particular application, switching windows, opening a folder, taking a screenshot or performing another supported desktop task.

PLUTO must maintain short-term context during the active session. The context should include the current application, current browser, current website, current URL, current page, previous command, previous action, current task, current search query, available results and recent actions. This context should be provided to the GPT-OSS 120B planner when necessary so that follow-up commands are understood naturally. If I say "choose the second one" after PLUTO has just performed a search, it should know what "one" refers to without asking unnecessary questions.

Implement a proper Python state machine for PLUTO. The system should have clear states including IDLE, LISTENING, THINKING, PLANNING, EXECUTING, VERIFYING, SPEAKING and ERROR. These states must also be communicated to the existing frontend so the PLUTO orb and interface can visually represent what the assistant is doing. When PLUTO hears my voice, the interface should enter listening or thinking mode, during execution it should show the executing state, after the action it should show verification, during ElevenLabs speech it should show speaking, and immediately afterward it should return to listening.

Use ElevenLabs for PLUTO's spoken responses. Responses should be short and natural instead of explaining every internal step. For example, after opening YouTube PLUTO can say **"YouTube is open, BOSS."** After completing a search it can say **"Searching Iron Man, BOSS."** After selecting the second result it can say **"Done, BOSS."** The detailed execution information can be shown visually in the PLUTO interface while the voice remains concise.

The Python backend should communicate with the React/Next.js frontend through a clean local API or WebSocket connection. The frontend should receive events containing the current PLUTO state, recognized speech, current action, execution status, verification status and final result. This allows the existing futuristic PLUTO interface to remain the visual layer while Python handles the actual autonomous computer interaction.

Start Level 1 with safe desktop and browser capabilities including opening applications, closing applications, opening URLs, opening files, opening folders, switching windows, taking screenshots, controlling volume, typing text, pressing keyboard keys, scrolling, clicking browser elements, searching websites and selecting search results. Keep the architecture modular because later PLUTO will need additional capabilities such as filesystem automation, email, calendar, coding, system management, persistent memory and more advanced autonomous workflows.

PLUTO must verify actions instead of assuming they succeeded. If it opens YouTube, it should check that the browser actually reached YouTube. If it performs a search, it should check that search results appeared. If it selects a video, it should verify that the expected video page opened. If an action fails, PLUTO should retry when the action is safe and reasonable. If it still cannot complete the task, it should explain the failure briefly and return to listening instead of becoming stuck.

Do not allow dangerous operations to happen automatically. Actions such as deleting important files, formatting drives, changing critical system configuration, installing unknown software or executing arbitrary shell commands should require an appropriate confirmation mechanism. Normal navigation, application opening, web searching and other safe Level 1 actions can be performed automatically.

The final result should make PLUTO feel like a **voice-controlled autonomous computer assistant rather than a voice chatbot**. I should be able to speak naturally, PLUTO should understand the current situation, perform the task, verify what happened, talk back to me and continue listening without requiring me to restart the interaction. Build the Level 1 foundation properly and modularly so that future levels can extend the same Python agent instead of replacing it.
e_machine.transition_to(PlutoState.LISTENING, session)
                
            except Exception as e:
                logger.error(f"Error in autonomous loop: {e}")
                await self.handle_error(e, session)
                await self.state_machine.transition_to(PlutoState.LISTENING, session)
```

---

## 🗂️ File Structure

```
pluto-backend/
├── app/
│   ├── agent/
│   │   ├── orchestrator_v2.py         # Main autonomous orchestrator
│   │   ├── state_machine.py           # PLUTO state management
│   │   ├── context_manager.py         # Session context tracking
│   │   ├── intent_parser.py           # Intent understanding
│   │   └── session_manager.py         # (existing, enhanced)
│   │
│   ├── tools/
│   │   ├── registry_v2.py             # Enhanced tool system
│   │   ├── application_tools.py       # App management
│   │   ├── browser_tools.py           # Browser control
│   │   ├── file_tools.py              # File operations
│   │   ├── system_tools.py            # System control
│   │   └── workspace_tools.py         # Workspace management
│   │
│   ├── automation/
│   │   ├── browser_engine.py          # Playwright browser automation
│   │   ├── page_analyzer.py           # Page type detection
│   │   ├── handlers/
│   │   │   ├── youtube_handler.py     # YouTube-specific logic
│   │   │   ├── google_handler.py      # Google-specific logic
│   │   │   ├── github_handler.py      # GitHub-specific logic
│   │   │   └── generic_handler.py     # Generic page handler
│   │   └── element_finder.py          # Smart element location
│   │
│   ├── verification/
│   │   ├── verifier.py                # Action verification
│   │   ├── retry_policy.py            # Retry logic
│   │   └── validators.py              # Validation helpers
│   │
│   ├── voice/
│   │   ├── pipeline_manager.py        # Voice pipeline control
│   │   ├── stt.py                     # Speech-to-text (enhanced)
│   │   ├── local_tts.py               # Text-to-speech (existing)
│   │   └── vad.py                     # Voice activity detection
│   │
│   ├── desktop/
│   │   ├── window_manager.py          # Linux window control
│   │   ├── application_manager.py     # App launching/closing
│   │   ├── screenshot.py              # Screenshot utilities
│   │   └── input_controller.py        # Keyboard/mouse control
│   │
│   └── schemas/
│       ├── tools.py                    # Tool schemas
│       ├── context.py                  # Context schemas
│       └── intent.py                   # Intent schemas
│
├── requirements.txt                    # Updated dependencies
└── tests/
    ├── test_orchestrator.py
    ├── test_tools.py
    ├── test_browser_engine.py
    └── test_verification.py
```

---

## 📦 Dependencies

**New Python Packages:**
```txt
# Browser Automation
playwright==1.41.0
playwright-stealth==0.0.1

# Voice Recognition
SpeechRecognition==3.10.1
pyaudio==0.2.14
pydub==0.25.1

# Desktop Automation
pyautogui==0.9.54
python-xlib==0.33  # Linux window management
pynput==1.7.6

# Process Management
psutil==5.9.7

# Image Processing (for verification)
pillow==10.2.0
opencv-python==4.9.0.80

# Existing
fastapi==0.109.0
uvicorn==0.27.0
httpx==0.26.0
gTTS==2.5.4
structlog==24.1.0
```

**System Dependencies (Linux):**
```bash
# Playwright browsers
playwright install chromium

# Audio
sudo apt-get install portaudio19-dev python3-pyaudio

# X11 (window management)
sudo apt-get install python3-xlib xdotool wmctrl

# Screenshot
sudo apt-get install scrot

# Optional: Voice activity detection
sudo apt-get install libopus0 libopusfile0
```

---

## 🔐 Safety & Security

### Safety Levels

```python
class SafetyLevel(Enum):
    SAFE = "safe"                    # Auto-execute
    CONFIRM_REQUIRED = "confirm"     # Ask user first
    DANGEROUS = "dangerous"          # Requires explicit permission + confirmation
```

### Safe Operations (Auto-Execute)
- Opening applications
- Opening URLs
- Browsing websites
- Searching
- Taking screenshots
- Opening files (read-only)
- Switching windows
- Adjusting volume
- Copying files (to safe locations)

### Confirm Required
- Closing applications
- Deleting files
- Moving files
- Renaming files
- Installing software
- Changing system settings
- Terminal commands

### Dangerous (Blocked by Default)
- Formatting drives
- Deleting system files
- Modifying critical configs
- Network security changes
- Arbitrary shell execution

### Path Validation
```python
ALLOWED_PATHS = [
    "~/Desktop",
    "~/Documents",
    "~/Downloads",
    "~/Projects",
    "~/Pictures",
]

BLOCKED_PATHS = [
    "/etc",
    "/sys",
    "/proc",
    "/boot",
    "~/.ssh",
]
```

---

## 🔄 Continuous Listening Implementation

### Voice Pipeline Flow

```python
class VoicePipelineManager:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_listening = False
        self.is_speaking = False
        
    async def continuous_listen(self, session: Session):
        """Main listening loop"""
        with self.microphone as source:
            # Adjust for ambient noise once
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            while session.active:
                if not self.is_speaking:  # Don't listen while PLUTO is speaking
                    try:
                        # Non-blocking listen with timeout
                        audio = await self.listen_async(source, timeout=5)
                        
                        if audio:
                            # Process in background
                            asyncio.create_task(self.process_audio(audio, session))
                    
                    except sr.WaitTimeoutError:
                        continue  # Just keep listening
                        
                await asyncio.sleep(0.1)
    
    async def on_tts_started(self):
        """Called when PLUTO starts speaking"""
        self.is_speaking = True
        # Optionally: play a short beep or show visual cue
    
    async def on_tts_finished(self):
        """Called when PLUTO finishes speaking"""
        self.is_speaking = False
        # Automatically resume listening
        await self.emit_event("listening_resumed")
```

### Frontend Integration

**WebSocket Events:**
```typescript
// Listening states
{
  type: "voice_state",
  state: "listening" | "processing" | "paused",
  waveform: number[]  // Optional: show voice waveform
}

// Auto-resume after TTS
{
  type: "tts_finished",
  message: "Ready for next command"
}
```

---

## 📊 Implementation Phases

### **Phase 1: Foundation (Week 1)**
- [ ] Set up new file structure
- [ ] Implement State Machine
- [ ] Implement Context Manager
- [ ] Create Tool Registry V2 architecture
- [ ] Set up Playwright browser engine
- [ ] Basic verification system

### **Phase 2: Core Tools (Week 2)**
- [ ] Application management tools
- [ ] Browser control tools
- [ ] File management tools
- [ ] System control tools
- [ ] Tool execution and verification

### **Phase 3: Browser Intelligence (Week 3)**
- [ ] Page analyzer
- [ ] YouTube handler
- [ ] Google handler
- [ ] Generic handler
- [ ] Smart element finding
- [ ] Search result selection

### **Phase 4: Voice Pipeline (Week 4)**
- [ ] Continuous STT with speech_recognition
- [ ] Voice activity detection
- [ ] Auto-resume after TTS
- [ ] Silence detection and timeout
- [ ] Integration with state machine

### **Phase 5: Orchestrator V2 (Week 5)**
- [ ] Autonomous control loop
- [ ] Intent parsing with context
- [ ] Multi-step execution
- [ ] Error handling and recovery
- [ ] State transitions

### **Phase 6: Context & Intelligence (Week 6)**
- [ ] Session context tracking
- [ ] Follow-up command understanding
- [ ] Short-term memory
- [ ] Context-aware responses

### **Phase 7: Integration & Testing (Week 7)**
- [ ] Frontend WebSocket updates
- [ ] Visual state indicators
- [ ] End-to-end testing
- [ ] Example workflows
- [ ] Performance optimization

### **Phase 8: Polish & Documentation (Week 8)**
- [ ] Error messages
- [ ] User feedback
- [ ] Documentation
- [ ] Demo videos
- [ ] Deployment guide

---

## 🧪 Testing Strategy

### Unit Tests
```python
# Test each tool independently
test_open_application()
test_browser_search()
test_verify_url()

# Test context management
test_context_creation()
test_context_updates()
test_context_retrieval()

# Test state transitions
test_state_machine_transitions()
test_invalid_transitions()
```

### Integration Tests
```python
# Test tool chains
test_open_youtube_and_search()
test_search_and_select_result()
test_multi_step_workflow()

# Test verification
test_action_verification()
test_retry_on_failure()
```

### End-to-End Tests
```python
# Full workflow tests
test_voice_to_execution_to_response()
test_continuous_commands()
test_context_aware_commands()
```

### Manual Test Cases

**Test Case 1: YouTube Video Search**
```
1. Say: "Open YouTube"
   ✓ Browser opens YouTube
   ✓ PLUTO says "YouTube is open, BOSS"
   ✓ Returns to listening

2. Say: "Search Iron Man"
   ✓ Search field activated
   ✓ "Iron Man" typed and searched
   ✓ PLUTO says "Searching Iron Man, BOSS"
   ✓ Returns to listening

3. Say: "Choose the second video"
   ✓ Second video identified
   ✓ Video clicked and opened
   ✓ PLUTO says "Done, BOSS"
   ✓ Returns to listening
```

**Test Case 2: Application Management**
```
1. Say: "Open VS Code"
   ✓ VS Code launches
   ✓ Window appears
   ✓ PLUTO confirms

2. Say: "Open Firefox"
   ✓ Firefox launches
   ✓ Both apps running
   ✓ PLUTO confirms

3. Say: "Switch to VS Code"
   ✓ VS Code window focused
   ✓ PLUTO confirms
```

**Test Case 3: File Operations**
```
1. Say: "Open my Downloads folder"
   ✓ File manager opens Downloads
   ✓ PLUTO confirms

2. Say: "Find files with 'report' in the name"
   ✓ Search executed
   ✓ Results shown
   ✓ PLUTO lists count

3. Say: "Open the first one"
   ✓ File opens
   ✓ PLUTO confirms
```

---

## 📈 Success Metrics

### Performance Targets
- **Command Recognition**: >95% accuracy
- **Intent Understanding**: >90% accuracy with context
- **Tool Execution Success**: >95%
- **Verification Accuracy**: >98%
- **Response Time**: <3 seconds (command to action)
- **TTS to Listening**: <0.5 seconds

### User Experience Goals
- Zero manual interventions for 90% of Level 1 commands
- Natural conversation flow
- Clear error messages
- Predictable behavior
- Fast response times

---

## 🚀 Future Levels (Roadmap)

### Level 2: Advanced Desktop Control
- Email management
- Calendar integration
- Advanced file operations
- System configuration
- Multi-monitor support

### Level 3: Coding & Development
- Code editing
- Git operations
- Terminal automation
- Project scaffolding
- Code review

### Level 4: Persistent Memory
- Long-term context
- User preferences
- Learning from corrections
- Routine automation
- Proactive suggestions

### Level 5: Full Autonomy
- Task decomposition
- Goal-oriented behavior
- Multi-step planning
- Self-correction
- Parallel task execution

---

## 📝 Notes & Considerations

### Linux-Specific Challenges
- Different desktop environments (GNOME, KDE, XFCE)
- Window manager variations
- Wayland vs X11
- Different application names across distros

**Solution**: Detect environment and adapt behavior

### Browser Automation Challenges
- Dynamic page content
- Anti-bot detection
- Loading delays
- Network issues

**Solution**: Smart waiting, retry logic, graceful degradation

### Voice Recognition Challenges
- Ambient noise
- Accent variations
- Background conversation
- Voice clipping

**Solution**: Noise cancellation, confidence thresholds, confirmation for low-confidence

---

## ✅ Definition of Done

Level 1 is complete when:

1. ✅ PLUTO can continuously listen without manual reactivation
2. ✅ Basic commands work: open app, open URL, search, select result
3. ✅ Context is maintained across follow-up commands
4. ✅ Actions are verified before confirming to user
5. ✅ TTS responses are concise and natural
6. ✅ Frontend shows correct states visually
7. ✅ Error handling is graceful
8. ✅ Safety checks prevent dangerous operations
9. ✅ All tests pass
10. ✅ Documentation is complete

---

**Status**: 📋 PLANNING COMPLETE - READY FOR IMPLEMENTATION

**Next Step**: Await approval to begin Phase 1 implementation

---

*Document created: September 6, 2026*  
*Author: Kiro AI Assistant*  
*Version: 1.0*
