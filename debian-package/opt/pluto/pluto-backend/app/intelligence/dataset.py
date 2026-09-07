"""PLUTO's own command->intent dataset.

This is the seed corpus PLUTO trains its local intent classifier on. It is
hand-authored and intentionally broad so the model generalises beyond exact
phrases. It is NOT a copy of any external dataset - it is PLUTO's own knowledge
base of how humans phrase computer-assistant commands.

Each theme maps to one high-level intent label. The planning step (see
``app/agent/nlu.py``) still produces the precise ordered tool plan; the ML
classifier here decides *what the user is trying to do* and a confidence score.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# Every intent the classifier can produce. Keep in sync with the labels in the
# dataset (and with what ``PlutoBrain`` / the planning layer understands).
INTENT_LABELS: List[str] = [
    "open_application",
    "close_application",
    "switch_application",
    "list_apps",
    "open_website",
    "browser_search",
    "browser_click",
    "browser_snapshot",
    "browser_control",
    "take_screenshot",
    "set_volume",
    "get_volume",
    "copy_to_clipboard",
    "get_clipboard",
    "list_files",
    "find_files",
    "create_folder",
    "create_file",
    "read_file",
    "open_file",
    "delete_file",
    "move_file",
    "copy_file",
    "get_processes",
    "kill_process",
    "send_message",
    "open_chat",
    "run_command",
    "system_status",
    "greeting",
    "thanks",
    "help",
    "identity",
]

# label -> example utterances (varied phrasing so the model generalises).
INTENT_EXAMPLES: Dict[str, List[str]] = {
    "open_application": [
        "open firefox", "launch vscode", "start the terminal",
        "open google chrome", "run spotify", "please open nautilus",
        "launch visual studio code", "start discord", "open the calculator",
        "launch the file manager", "open sublime text", "start vlc",
        "run gnome terminal", "open settings app", "start up the browser",
        "launch the terminal app", "open the gimp editor", "start inkscape",
        "run the file manager", "launch a terminal window",
        "open the code editor", "start up signal", "launch zotero",
    ],
    "close_application": [
        "close firefox", "quit vscode", "exit the terminal",
        "close chrome", "shut down slack", "quit discord",
        "close spotify", "kill the browser program", "stop the calculator",
        "close the file manager", "quit the editor", "exit signal",
        "terminate the running app", "end the program", "shut the app",
    ],
    "switch_application": [
        "switch to firefox", "focus on vscode", "switch to the terminal",
        "bring up the browser", "switch over to chrome", "go to the code editor",
        "focus the file manager", "switch to the settings window",
        "jump to the browser", "switch to discord", "focus on the calculator",
        "bring the terminal to front", "switch window to firefox",
    ],
    "list_apps": [
        "what apps are running", "list running applications",
        "show running apps", "which applications are open",
        "what programs are running", "list the open apps",
        "whats running on my desktop", "show open applications",
        "list all running programs", "what windows are open",
        "display the running apps", "show me the active applications",
    ],
    "open_website": [
        "open youtube", "go to github", "open google", "visit reddit",
        "open twitter", "launch gmail", "take me to wikipedia",
        "open example.com", "go to the openai website", "open youtube.com",
        "navigate to stackoverflow", "open the google docs site",
        "visit amazon", "take me to reddit", "open the netflix homepage",
        "launch the maps app website", "go to bing", "open the x site",
        "browse to duckduckgo", "open a web page",
    ],
    "browser_search": [
        "search for iron man on youtube", "search google for python tutorials",
        "look up machine learning", "find me a recipe for pasta",
        "search the web for the news", "google the weather in paris",
        "search youtube for lofi beats", "look for the best laptop reviews",
        "find information on quantum computing", "search for how to cook rice",
        "look up the capital of australia", "google python list comprehension",
        "search wikipedia for the eiffel tower", "find videos about space",
        "search the internet for movie trailers", "look for a good hiking trail",
        "search github for react projects", "find me a map of london",
    ],
    "browser_click": [
        "play the second video", "open the first result",
        "click the third link", "choose the top result",
        "select the first video", "click the next one",
        "open result number two", "play that video",
        "go to the first search result", "click the second item",
        "open the fourth result", "select the fifth video",
        "click the link about news", "open the top article",
    ],
    "browser_snapshot": [
        "whats on the screen right now", "what is on the page",
        "read the page", "snapshot the browser",
        "what do you see on this webpage", "whats open in the browser",
        "summarize the current page", "tell me the page title",
        "what links are on this page", "describe what's displayed",
    ],
    "browser_control": [
        "refresh the page", "reload the page", "go fullscreen",
        "make the browser fullscreen", "close the browser",
        "quit the browser", "press tab", "press enter", "scroll down",
        "go back", "go forward", "zoom in", "zoom out",
        "close the tab", "open a new tab", "focus the address bar",
        "type into the search box", "press control l",
    ],
    "take_screenshot": [
        "take a screenshot", "screenshot", "capture my screen",
        "take a screen capture", "grab a screenshot", "snapshot of the screen",
        "print screen", "capture the screen", "take a picture of the desktop",
        "screenshot the window", "screenshot the active window",
        "capture the full screen", "screen capture now",
        "take a screenshot of this area", "grab the display",
        "snap the screen", "capture the region", "take a photo of the screen",
    ],
    "set_volume": [
        "set volume to 40", "turn the volume up to 50", "lower the volume",
        "mute the sound", "unmute the audio", "make it louder",
        "set the volume to maximum", "turn the sound down",
        "volume to 30", "change the audio level", "adjust the volume",
        "set sound to 60 percent", "increase the volume", "decrease the volume",
        "turn up the audio", "quiet the audio", "volume up", "volume down",
    ],
    "get_volume": [
        "what is the volume", "check the volume", "how loud is the audio",
        "show me the current volume", "what volume am I at",
        "read the volume level", "tell me the audio level", "is it muted",
    ],
    "copy_to_clipboard": [
        "copy hello world to the clipboard", "put this text on the clipboard",
        "copy that to clipboard", "save to clipboard", "set the clipboard to my name",
        "copy the selected text", "send text to clipboard",
        "put my email on the clipboard", "store this on the clipboard",
    ],
    "get_clipboard": [
        "whats on my clipboard", "read the clipboard",
        "show the clipboard contents", "paste from clipboard",
        "check the clipboard", "get the clipboard text",
        "what did I copy", "show me the clipboard",
    ],
    "list_files": [
        "list files in my documents", "list the files here",
        "whats in my downloads", "show the files in this folder",
        "list directory contents", "whats inside the project folder",
        "show me the files", "list the contents of desktop",
        "what files do I have", "show directory", "ls the current folder",
        "list items in the home folder",
    ],
    "find_files": [
        "find files matching budget", "search for the report pdf",
        "look for my resume file", "find a file named notes",
        "search for documents with invoice", "where is my photo",
        "find all files named report", "search for the presentation",
        "locate the budget spreadsheet", "find my tax documents",
        "search the folder for images", "look for a file containing summary",
    ],
    "create_folder": [
        "create a folder called reports", "make a new folder for project",
        "create a directory named work", "new folder called images",
        "make a folder in documents", "create folder budget",
        "mkdir project folder", "create a folder on the desktop",
        "make a directory for music", "add a new folder",
    ],
    "create_file": [
        "create a file called notes.txt saying hello",
        "make a new file for the notes", "write a file called readme",
        "create a text file", "make a file named todo",
        "create a file with hello world content",
        "new file called config.json", "write my notes to a file",
        "create a markdown file", "save this to a new file",
    ],
    "read_file": [
        "read the file notes.txt", "show me the contents of readme",
        "open the file and show its content", "cat the file config",
        "display the document", "read my notes file",
        "show the first lines of the log", "print the file content",
        "read the config file", "view the readme",
    ],
    "open_file": [
        "open the file report.pdf", "open notes.txt", "open this document",
        "launch the image file", "open my resume", "open the spreadsheet",
        "open the presentation file", "launch the pdf",
        "double click on the file", "open the attachment",
    ],
    "delete_file": [
        "delete the file old-report.txt", "remove the temp file",
        "delete this file", "move the document to trash", "erase the file",
        "delete the folder work", "remove old logs", "delete the screenshot",
        "trash the notes file", "clean up the temp files",
    ],
    "move_file": [
        "move report.pdf from downloads to documents",
        "move the file notes.txt to projects", "rename notes.txt to diary.txt",
        "move file to a new folder", "rename the file to new name",
        "move the document to the desktop", "relocate the image",
        "rename folder work to tasks",
    ],
    "copy_file": [
        "copy the file notes.txt from documents to downloads",
        "copy report.pdf to the desktop", "duplicate this file",
        "make a copy of the notes", "copy the image to pictures",
        "back up the document", "copy the folder to another place",
    ],
    "get_processes": [
        "is spotify running", "check if chrome is running",
        "show me the top processes", "list running processes",
        "what processes are using the most cpu", "is firefox running",
        "show the process list", "whats using my memory",
        "show running programs", "check if the server is up",
    ],
    "kill_process": [
        "stop the process named firefox", "kill chrome",
        "terminate the spotify process", "kill the process", "end the task",
        "kill the python process", "force quit the app", "stop the server",
        "terminate the hung program", "kill process by name",
    ],
    "send_message": [
        "send a whatsapp message to mom saying I will be late",
        "message sam on telegram", "text John that the build passed",
        "send him a message on whatsapp", "send a signal message to team",
        "whatsapp Sarah saying good morning", "send mom a text",
        "message the group that I am on my way", "email is not wanted",
        "send a message to the client", "tell Sam the meeting moved",
    ],
    "open_chat": [
        "open whatsapp", "launch telegram", "open the signal app",
        "start whatsapp web", "open telegram web", "launch the chat app",
    ],
    "run_command": [
        "run ls -la", "execute pwd in the terminal", "run the command df -h",
        "exec git status", "run whoami", "execute the command uname -a",
        "run a terminal command", "run python3 -v", "execute ls",
        "run the script", "run make build", "execute the test suite",
    ],
    "system_status": [
        "check system status", "show system stats", "how is my cpu doing",
        "display system info", "what is my disk usage", "show memory usage",
        "system health check", "show the uptime", "report system performance",
        "how is the computer running", "show battery status",
        "check the system resources", "what is my gpu usage",
    ],
    "greeting": [
        "hello", "hi pluto", "hey there", "good morning", "howdy", "hiya",
        "whats up", "yo", "hi", "hello pluto", "good evening", "good afternoon",
        "hey", "sup", "greetings",
    ],
    "thanks": [
        "thank you", "thanks a lot", "appreciate it", "good job pluto",
        "nice work", "well done", "awesome thanks", "much obliged",
        "thanks for the help", "great job", "perfect thank you",
    ],
    "help": [
        "what can you do", "help me", "show me your capabilities",
        "list your skills", "what commands do you know", "what tools do you have",
        "give me a list of commands", "show what you can automate",
        "help with a task", "explain your features",
    ],
    "identity": [
        "who are you", "what are you", "introduce yourself", "what is your name",
        "tell me about yourself", "whats your name", "are you an ai",
        "are you pluto", "describe yourself",
    ],
}


def build_dataset() -> List[Tuple[str, str]]:
    """Flatten the examples into ``[(text, intent), ...]`` pairs."""
    rows: List[Tuple[str, str]] = []
    for label, examples in INTENT_EXAMPLES.items():
        for text in examples:
            rows.append((text, label))
    return rows


def load_dataset() -> List[Tuple[str, str]]:
    """Public helper (kept for symmetry; returns the seed corpus)."""
    return build_dataset()
