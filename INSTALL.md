# Installing PLUTO (Debian package)

## Quick install

```bash
sudo apt install ./dist/Pluto_1.0.0_amd64.deb
# or: sudo dpkg -i ./dist/Pluto_1.0.0_amd64.deb
```

The package installs:

- `/usr/bin/pluto` — the native Tauri/Rust binary
- `/usr/share/applications/Pluto.desktop` — application-menu entry (`Exec=pluto`)
- `/usr/share/icons/hicolor/**/apps/pluto.png` — icons (from `pluto.png`)

Launch from the application menu ("PLUTO") or run `pluto` in a terminal.

## After installation

You do **not** need Python, Node.js, pip, venv, FastAPI, uvicorn, PyWebView or any
development server. PLUTO is a single native binary with the UI embedded.

## Recommended optional tools

PLUTO uses whatever is available and degrades gracefully:

- Screenshots: `xcap` (built-in, X11) — or any of `scrot`, `gnome-screenshot`, `grim` (+`slurp` on Wayland), `spectacle`, `imagemagick`
- Voice output (auto-detected, best first): Piper neural voices under
  `~/.local/share/piper-voices` or `/usr/share/piper-voices`, or `pico2wave`
  (`libttspico-utils`), or `espeak-ng` (female +f3 variant) — espeak is the
  final fallback. Install a Piper voice for the most natural speech:
  `sudo apt install piper` and put `en_US-amy.onnx` (etc.) under
  `~/.local/share/piper-voices/en/en_US/amy/` (also settable via `PLUTO_PIPER_VOICE`)
- Voice input: native microphone capture is built in; add `whisper-cli` from
  whisper.cpp + a small model at `~/.cache/pluto/ggml-base.en.bin` (~75 MB,
  external download — never bundled) or set `PLUTO_WHISPER_MODEL`
- Browser/window control: `xdotool`, `wmctrl`

```bash
sudo apt install espeak-ng pico2wave scrot xdotool wmctrl   # espeak-ng is enough to start
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
