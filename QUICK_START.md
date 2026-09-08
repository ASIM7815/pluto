# PLUTO Quick Start

## Run the desktop app

```bash
# Development (needs Rust + Tauri system deps on the build machine)
npm install
npm run tauri:dev

# Production .deb
npm run build:deb
sudo apt install ./dist/Pluto_1.0.0_amd64.deb
pluto
```

## Try these

| Say or type | What happens |
| --- | --- |
| `Open YouTube and play a song` | Browser opens YouTube, search runs, result selected |
| `Take a screenshot` | Saves to `~/Pictures/pluto_screenshot_*.png` (X11 native or Wayland tool) |
| `Copy "hello boss" to clipboard` | Native Rust clipboard write |
| `What's in my clipboard?` | Native clipboard read |
| `Create a folder called PLUTO inside my Projects directory` | Real folder under `~/Projects/PLUTO` |
| `Create a file called notes.txt in Documents with content "meeting at 5pm"` | Real file with content |
| `Open vscode` | Launches VS Code (`code`), verified running |
| `Check system status` | CPU/RAM/disk + running processes |
| `Run the command ls -la` | Executes as argv (no shell) with output |
| `Delete the file notes.txt in Documents` | **Asks for confirmation** before deleting |
| `Run the command rm -rf /` | Blocked by security policy |
| `What can you do?` | Capabilities readout |

Everything runs locally: screenshots, clipboard, files, processes, apps, TTS.
The webview is a real Tauri window — no Chrome tab, no ports.
