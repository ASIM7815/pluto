# 📦 PLUTO .deb Package

## Package Information

**File**: `pluto-ai_1.0.0_amd64.deb`  
**Size**: ~13 MB  
**Architecture**: amd64 (64-bit)  
**Platform**: Ubuntu 20.04+, Debian 11+

---

## ✨ What's Included

- ✅ PLUTO Backend (Python FastAPI + Local Intelligence)
- ✅ PLUTO Frontend (Next.js React UI)
- ✅ Pattern-based command matching (NO AI API costs)
- ✅ Local learning and memory system
- ✅ Browser automation with Playwright
- ✅ System integration (screenshots, clipboard, volume)
- ✅ Desktop launcher and icon
- ✅ Command-line utility (`pluto`)

---

## 🚀 Quick Install

```bash
# Install PLUTO
sudo dpkg -i pluto-ai_1.0.0_amd64.deb

# Install missing dependencies (if any)
sudo apt-get install -f

# Start PLUTO
pluto
```

**PLUTO will open automatically in your browser at http://localhost:3000**

---

## 📋 Dependencies

The package automatically installs these if missing:
- Python 3.10+
- Node.js 18+
- scrot (screenshots)
- xclip (clipboard)
- wmctrl (window management)
- xdotool (keyboard/mouse automation)
- Chromium or Google Chrome

---

## 🎯 Installation Locations

```
/opt/pluto/                          # Main application directory
├── pluto-backend/                   # Backend server
│   ├── app/                         # Python application
│   ├── venv/                        # Python virtual environment (created on install)
│   ├── .env                         # Configuration
│   └── requirements.txt             # Python dependencies
├── src/                             # Frontend source
├── public/                          # Static assets
├── package.json                     # Node.js dependencies
└── start.sh                         # Startup script

/usr/bin/pluto                       # Command-line shortcut
/usr/share/applications/pluto-ai.desktop  # Desktop entry
/usr/share/icons/.../pluto-ai.svg    # Application icon
~/.pluto/                            # User data (config, memory, browser profile)
```

---

## 🔧 Post-Installation

### First Run
On first start, PLUTO will:
1. Create Python virtual environment
2. Install Python dependencies
3. Install Playwright browsers (~200MB download)
4. Create user config directory (`~/.pluto/`)
5. Start backend and frontend servers
6. Open browser automatically

**This takes 2-5 minutes depending on your internet speed.**

### Verify Installation

```bash
# Check package is installed
dpkg -l | grep pluto-ai

# Check PLUTO command is available
which pluto

# Test backend
curl http://localhost:8765/health

# Check desktop entry
ls /usr/share/applications/pluto-ai.desktop
```

---

## 🎮 Usage

### Start PLUTO

**Option 1: Applications Menu**
- Open Applications → Search "PLUTO AI Assistant" → Click

**Option 2: Command Line**
```bash
pluto
```

**Option 3: Direct Script**
```bash
/opt/pluto/start.sh
```

### Try Commands
Once PLUTO is running at http://localhost:3000, try:

- "Open YouTube"
- "Take a screenshot"
- "Search for cats on YouTube"
- "Set volume to 50"
- "List running apps"

---

## 🔄 Updating

```bash
# Download new version
wget https://github.com/ASIM7815/pluto/releases/latest/download/pluto-ai_1.0.0_amd64.deb

# Install update (preserves your settings)
sudo dpkg -i pluto-ai_1.0.0_amd64.deb
```

---

## 🗑️ Uninstalling

```bash
# Remove PLUTO (keeps settings)
sudo apt-get remove pluto-ai

# Remove PLUTO and all settings
sudo apt-get purge pluto-ai
rm -rf ~/.pluto/
```

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Kill existing processes
pkill -f pluto-backend
pkill -f "next dev"

# Or use different ports (edit /opt/pluto/pluto-backend/.env)
```

### Browser Automation Fails
```bash
# Reinstall Playwright browsers
cd /opt/pluto/pluto-backend
source venv/bin/activate
python -m playwright install chromium
```

### Missing Dependencies
```bash
# Install manually
sudo apt-get install python3 python3-pip python3-venv \
  nodejs npm scrot xclip wmctrl xdotool chromium-browser
```

### Permission Denied
```bash
# Fix ownership
sudo chown -R $USER:$USER ~/.pluto/
sudo chown -R $USER:$USER /opt/pluto/
```

---

## 💰 Cost

**$0 - 100% FREE FOREVER**

- ❌ No API costs
- ❌ No subscriptions
- ❌ No cloud services
- ✅ Runs completely offline
- ✅ Local intelligence
- ✅ Privacy-first

---

## 🔒 Privacy

PLUTO is **privacy-first**:
- ✅ Everything runs locally on your machine
- ✅ No data sent to external servers
- ✅ No API calls to cloud services
- ✅ Your commands and data never leave your computer
- ✅ Browser profile stays local

---

## 📊 System Requirements

**Minimum**:
- Ubuntu 20.04 / Debian 11 (amd64)
- 4GB RAM
- 1GB free disk space
- Python 3.10+
- Node.js 18+

**Recommended**:
- Ubuntu 22.04 / Debian 12
- 8GB RAM
- 2GB free disk space
- Fast internet (first install only)

---

## 🏗️ Build Your Own Package

Want to customize or rebuild?

```bash
# Clone repository
git clone https://github.com/ASIM7815/pluto.git
cd pluto

# The debian-package/ directory contains the package structure
# Modify as needed, then rebuild:
dpkg-deb --build debian-package pluto-ai_1.0.0_amd64.deb
```

---

## 📚 Documentation

- **Installation Guide**: See `INSTALL.md`
- **Pattern Mode**: See `PATTERN_MODE_README.md`
- **Backend Intelligence**: See `pluto-backend/INTELLIGENCE.md`
- **Main README**: See `README.md`

---

## 🆘 Support

- **Issues**: https://github.com/ASIM7815/pluto/issues
- **Discussions**: https://github.com/ASIM7815/pluto/discussions
- **Documentation**: https://github.com/ASIM7815/pluto

---

## ✅ Package Checksum

Verify package integrity:
```bash
sha256sum pluto-ai_1.0.0_amd64.deb
```

---

## 📦 Package Details

```
Package: pluto-ai
Version: 1.0.0
Architecture: amd64
Installed-Size: ~50 MB
Depends: python3 (>= 3.10), python3-pip, nodejs (>= 18.0.0), 
         scrot, xclip, wmctrl, xdotool, 
         chromium-browser | google-chrome-stable
Section: utils
Priority: optional
Homepage: https://github.com/ASIM7815/pluto
Description: PLUTO - Local AI Desktop Assistant
 100% free, privacy-first AI assistant for Linux.
 Pattern-based command matching, local intelligence,
 browser automation, system control, and more.
 No API costs, works completely offline.
```

---

## 🎉 Ready to Install?

```bash
sudo dpkg -i pluto-ai_1.0.0_amd64.deb
sudo apt-get install -f
pluto
```

**Enjoy your 100% FREE AI assistant!** 🚀
