# 🎉 PLUTO .deb Package - Native Desktop Version

## 📦 Package Details

**File**: `dist/PLUTO_1.0.0_amd64.deb`  
**Size**: 310 MB  
**Type**: Native Linux Desktop Application  
**Architecture**: amd64  
**Created**: September 8, 2026

---

## ✨ Features

### Native Desktop Experience
✅ **Runs as native Linux window** - No browser needed!  
✅ **PyWebView integration** - Real desktop app, not web wrapper  
✅ **Production build** - Static Next.js files (no dev server)  
✅ **Desktop launcher** - Shows in Applications menu  
✅ **System integration** - Proper Linux desktop application  

### What's Included
- Complete PLUTO React/Next.js UI (static build)
- Python backend source code (optional)
- PyWebView native window framework
- Desktop entry and icons
- All dependencies in one package

---

## 🚀 Installation

```bash
# Install the package
sudo dpkg -i dist/PLUTO_1.0.0_amd64.deb

# Install any missing dependencies
sudo apt-get install -f

# Launch PLUTO
pluto
```

Or launch from **Applications menu** → Search "PLUTO"

---

## 📋 System Requirements

### Required
- **OS**: Ubuntu 20.04+ or Debian 11+ (amd64)
- **Python**: 3.10 or higher
- **GTK**: 3.0 (usually pre-installed)
- **WebKit2GTK**: For native window rendering
- **OpenGL**: For 3D graphics

### Dependencies (auto-installed)
```
python3 (>= 3.10)
python3-pip
python3-gi
gir1.2-gtk-3.0
libgtk-3-0
libwebkit2gtk-4.1-0    # Ubuntu 24.04 compatible
libgl1
```

**Note**: Ubuntu 24.04 uses `libwebkit2gtk-4.1-0`. The package is configured correctly for this version.

---

## 🎯 How It Works

1. **Native Window**: Uses PyWebView to create a real Linux desktop window
2. **Static Frontend**: Pre-built Next.js app (no localhost server needed)
3. **Optional Backend**: Python FastAPI backend included for advanced features
4. **Desktop Integration**: Proper .desktop file, icons, and launcher

---

## 📊 Package Contents

```
/opt/pluto/
├── out/                    # Static Next.js build
├── venv/                   # Python venv with pywebview
├── pluto-backend/         # Backend source (optional)
├── pluto-app.py           # Python launcher
└── pluto.png              # Application logo

/usr/bin/pluto             # Launch command
/usr/share/applications/   # Desktop entry
/usr/share/icons/          # App icons (multiple sizes)
```

**Total installed size**: ~500 MB

---

## 💡 Advantages Over Browser Version

### Native Desktop Version (This Package)
✅ Runs as real desktop app  
✅ No browser dependency  
✅ Faster startup  
✅ Lower memory usage  
✅ Professional appearance  
✅ Better system integration  

### Browser Version (Previous)
✅ Full development environment  
✅ Browser automation tools (Playwright)  
✅ Hot reload for development  
✅ Easier debugging  
✅ Smaller download size (13 MB)  

---

## 🎮 Usage

### Launching
```bash
# From terminal
pluto

# Or from Applications menu
# Search for "PLUTO" and click
```

### Features Available
- 🎤 Voice commands
- 💬 Natural language interface
- 🎨 Animated orb interface
- ⚙️ System tools (if backend enabled)
- 📊 Activity tracking
- 🎯 Quick actions

---

## 🔧 Advanced Configuration

### Enable Backend Features

The package includes the Python backend source. To enable:

```bash
cd /opt/pluto/pluto-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./start.sh
```

Backend features include:
- Browser automation
- System control (screenshots, clipboard)
- Window management
- File operations
- Advanced AI features

---

## 🗑️ Uninstallation

```bash
# Remove PLUTO
sudo apt-get remove pluto

# Remove PLUTO and all config
sudo apt-get purge pluto
```

User data in `~/.pluto/` is preserved. Delete manually if needed:
```bash
rm -rf ~/.pluto/
```

---

## 🐛 Troubleshooting

### Package won't install
```bash
# Install missing dependencies
sudo apt-get install -f

# Or manually install GTK dependencies
sudo apt-get install python3-gi gir1.2-gtk-3.0 libgtk-3-0 libwebkit2gtk-4.0-37
```

### Application won't start
```bash
# Check logs
journalctl -xe | grep pluto

# Verify Python
python3 --version  # Should be 3.10+

# Check venv
ls -la /opt/pluto/venv/
```

### Missing icons
```bash
# Update icon cache
sudo update-icon-caches /usr/share/icons/hicolor
sudo update-desktop-database /usr/share/applications
```

---

## 💰 Cost

**$0 - 100% FREE FOREVER**

✅ No API costs  
✅ No subscriptions  
✅ No cloud services  
✅ Runs completely offline  
✅ Privacy-first  

---

## 📚 Documentation

- **Main README**: `README.md`
- **Pattern Mode**: `PATTERN_MODE_README.md`
- **Backend Intelligence**: `pluto-backend/INTELLIGENCE.md`
- **Installation**: `INSTALL.md`

---

## 🔗 Distribution

### Upload to GitHub Releases

1. Go to https://github.com/ASIM7815/pluto/releases
2. Click "Create a new release"
3. Tag: `v1.0.0`
4. Title: "PLUTO v1.0.0 - Native Desktop"
5. Upload: `dist/PLUTO_1.0.0_amd64.deb`
6. Publish!

### Users Download & Install

```bash
wget https://github.com/ASIM7815/pluto/releases/download/v1.0.0/PLUTO_1.0.0_amd64.deb
sudo dpkg -i PLUTO_1.0.0_amd64.deb
sudo apt-get install -f
pluto
```

---

## 🎯 Target Audience

Perfect for:
- 👨‍💼 End users who want a desktop AI assistant
- 🏢 Organizations deploying to Ubuntu/Debian workstations
- 🎓 Students learning AI and desktop development
- 💻 Anyone who prefers native apps over browser-based tools

---

## 📝 Technical Details

### Build Process
1. Next.js production build (`npm run build`)
2. Python venv creation with pywebview
3. Icon generation (multiple sizes)
4. Debian package assembly
5. dpkg-deb packaging

### Technologies
- **Frontend**: React 19, Next.js 15, Tailwind CSS, Framer Motion
- **Desktop**: PyWebView 5.0+, GTK 3.0, WebKit2GTK
- **Backend** (optional): Python 3.10+, FastAPI, Playwright
- **Packaging**: Debian .deb format

---

## 🆘 Support

- **Issues**: https://github.com/ASIM7815/pluto/issues
- **Discussions**: https://github.com/ASIM7815/pluto/discussions
- **Documentation**: https://github.com/ASIM7815/pluto

---

## ✅ Ready to Ship!

Your PLUTO native desktop application is packaged and ready for distribution. Users get a professional Linux desktop experience with zero API costs and complete privacy.

**🚀 Distribute with confidence!**
