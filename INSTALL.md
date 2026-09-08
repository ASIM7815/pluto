# Installing PLUTO (Debian package)

## Quick install

```bash
sudo apt install ./dist/Pluto_1.0.0_amd64.deb
# or: sudo dpkg -i ./dist/Pluto_1.0.0_amd64.deb
```

The package installs:

- `/usr/bin/pluto` — the native Tauri/Rust binary
- `/usr/share/applications/pluto.desktop` — application-menu entry
- `/usr/share/icons/hicolor/**/apps/pluto.png` — icons (from `pluto.png`)

Launch from the application menu ("PLUTO") or run `pluto` in a terminal.

## After installation

You do **not** need Python, Node.js, pip, venv, FastAPI, uvicorn, PyWebView or any
development server. PLUTO is a single native binary with the UI embedded.

## Recommended optional tools

PLUTO uses whatever is available and degrades gracefully:

- Screenshots: `xcap` (built-in, X11) — or any of `scrot`, `gnome-screenshot`, `grim` (+`slurp` on Wayland), `spectacle`, `imagemagick`
- Voice output: `espeak-ng` (recommended, offline TTS)
- Voice input: `whisper-cli` from whisper.cpp + a model at `~/.cache/pluto/ggml-*.bin` (or `PLUTO_WHISPER_MODEL`)
- Browser/window control: `xdotool`, `wmctrl`

```bash
sudo apt install espeak-ng scrot xdotool wmctrl
```

## Verify the install

```bash
dpkg -I dist/Pluto_1.0.0_amd64.deb        # metadata
dpkg -c dist/Pluto_1.0.0_amd64.deb        # contents
pluto                                     # launch the app
```

## Uninstall

```bash
sudo apt remove pluto
```
