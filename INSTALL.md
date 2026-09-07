# PLUTO AI Assistant - Installation Guide

## 📦 Installing PLUTO on Linux

### Option 1: Install from .deb package (Recommended)

```bash
# Install the package
sudo dpkg -i pluto-ai_1.0.0_amd64.deb

# Install any missing dependencies
sudo apt-get install -f
```

That's it! PLUTO is now installed.

---

## 🚀 Starting PLUTO

### From Applications Menu
1. Open your Applications menu
2. Search for "PLUTO AI Assistant"
3. Click to launch

### From Command Line
```bash
# Start PLUTO
pluto

# Or directly
/opt/pluto/start.sh
```

PLUTO will open in your browser at: **http://localhost:3000**

---

## 🎯 What Gets Installed

- **Backend**: `/opt/pluto/pluto-backend/` - Python FastAPI server
- **Frontend**: `/opt/pluto/` - Next.js web interface
- **Start Script**: `/usr/bin/pluto` - Command to launch PLUTO
- **Desktop Entry**: `/usr/share/applications/pluto-ai.desktop`
- **Icon**: `/usr/share/icons/hicolor/256x256/apps/pluto-ai.svg`
- **Config**: `~/.pluto/` - User configuration and data

---

## 📋 System Requirements

### Required
- **OS**: Ubuntu 20.04+ or Debian 11+ (amd64)
- **Python**: 3.10 or higher
- **Node.js**: 18.0 or higher
- **System Tools**: scrot, xclip, wmctrl, xdotool
- **Browser**: Chromium or Google Chrome

### Recommended
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 500MB for installation + 1GB for browser automation
- **Display**: GUI environment (X11 or Wayland)

---

## 🔧 Post-Installation

### First Time Setup

1. **Start PLUTO**: Run `pluto` or launch from applications menu
2. **Wait for setup**: First start downloads browser automation tools (~200MB)
3. **Access interface**: Browser opens automatically at http://localhost:3000
4. **Try a command**: Say "Open YouTube" or "Take a screenshot"

### Verify Installation

```bash
# Check PLUTO is installed
dpkg -l | grep pluto-ai

# Check system dependencies
which python3 nodejs scrot xclip wmctrl xdotool

# Test backend health
curl http://localhost:8765/health
```

---

## 🎤 Voice Setup (Optional)

PLUTO works with keyboard input by default. For voice commands:

1. Click the microphone button in the UI
2. Grant browser microphone permission
3. Speak your command

---

## ⚙️ Configuration

Configuration files are stored in `~/.pluto/`:
- `pluto.db` - Memory and learning data
- `browser-profile/` - Browser session data (stays logged in)

Backend config: `/opt/pluto/pluto-backend/.env`

---

## 🔄 Updating PLUTO

```bash
# Download new version
wget https://github.com/ASIM7815/pluto/releases/latest/pluto-ai_1.0.0_amd64.deb

# Install update (keeps your data)
sudo dpkg -i pluto-ai_1.0.0_amd64.deb
```

---

## 🗑️ Uninstalling PLUTO

```bash
# Remove PLUTO
sudo apt-get remove pluto-ai

# Remove PLUTO and configuration
sudo apt-get purge pluto-ai

# Remove dependencies (if not needed by other packages)
sudo apt-get autoremove
```

Your personal data in `~/.pluto/` is kept even after purge. Delete manually if needed:
```bash
rm -rf ~/.pluto/
```

---

## 🐛 Troubleshooting

### PLUTO won't start
```bash
# Check if ports are in use
sudo lsof -i :3000
sudo lsof -i :8765

# Check logs
journalctl -xe | grep pluto
```

### Missing dependencies
```bash
# Install all dependencies manually
sudo apt-get install python3 python3-pip python3-venv nodejs npm \
  scrot xclip wmctrl xdotool chromium-browser
```

### Browser automation not working
```bash
# Reinstall Playwright browsers
cd /opt/pluto/pluto-backend
source venv/bin/activate
python -m playwright install chromium
```

### Permission denied errors
```bash
# Fix permissions
sudo chown -R $USER:$USER ~/.pluto/
```

---

## 💡 Features

✅ **100% FREE** - No API costs, works completely offline  
✅ **Local Intelligence** - Privacy-first, learns from you  
✅ **Voice Commands** - Natural language understanding  
✅ **Browser Automation** - Control Chrome, search, click  
✅ **System Control** - Screenshots, clipboard, volume  
✅ **Window Management** - Switch apps, manage windows  
✅ **Memory** - Remembers context and past actions  

---

## 📚 Examples

Try these commands:
- "Open YouTube"
- "Take a screenshot"
- "Search for cats on YouTube"
- "Set volume to 50"
- "List running apps"
- "Copy this to clipboard"

---

## 🆘 Support

- **Issues**: https://github.com/ASIM7815/pluto/issues
- **Documentation**: https://github.com/ASIM7815/pluto
- **Backend Status**: http://localhost:8765/health

---

## 📄 License

PLUTO AI Assistant is open source software.
Check the repository for license details.
