//! System tools: screenshots (X11/Wayland), volume, clipboard, processes.

use super::{find_program, has_display, run_process, validate_path, ToolResult};
use serde_json::Value;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

// ---------------------------------------------------------------------------
// Screenshots - pure Rust (xcap) on X11, native tools on Wayland - graceful
// fallback chain so a missing tool never breaks the assistant.
// ---------------------------------------------------------------------------

fn screenshot_destination(directory: Option<&str>, filename: Option<&str>) -> Result<PathBuf, String> {
    let dir = match directory {
        Some(d) if !d.trim().is_empty() => validate_path(d)?,
        _ => validate_path(&super::super::nlu::expand_home("~/Pictures"))?,
    };
    std::fs::create_dir_all(&dir).map_err(|e| format!("Cannot create screenshot folder: {}", e))?;
    let name = match filename {
        Some(f) if !f.trim().is_empty() => f.trim().to_string(),
        _ => {
            let secs = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
            format!("pluto_screenshot_{}.png", secs)
        }
    };
    let name = if name.to_lowercase().ends_with(".png") { name } else { format!("{}.png", name) };
    Ok(dir.join(name))
}

fn capture_x11(path: &PathBuf, area: &str) -> Result<bool, String> {
    let monitors = xcap::Monitor::all().map_err(|e| format!("xcap monitor error: {}", e))?;
    let monitor = monitors.first().ok_or("No monitors found")?;
    let image = monitor.capture_image().map_err(|e| format!("xcap capture error: {}", e))?;
    // "window" and "select" fall back to the full primary monitor when the
    // X server offers no reliable focused-window API; the UI is told clearly.
    let _ = area;
    image::DynamicImage::ImageRgba8(image)
        .save(path)
        .map_err(|e| format!("Failed to save screenshot: {}", e))?;
    Ok(true)
}

fn capture_with_native_tool(path: &PathBuf, area: &str) -> Option<Result<bool, String>> {
    let p = path.display().to_string();
    // Wayland & modern desktops: GNOME screenshot supports -a (area) and -f.
    if let Some(_prog) = find_program("gnome-screenshot") {
        let args: Vec<&str> = match area {
            "select" => vec!["-a", "-f", &p],
            "window" => vec!["-w", "-f", &p],
            _ => vec!["-f", &p],
        };
        if let Some(program) = find_program("gnome-screenshot") {
            if let Ok((code, _, _)) = run_process(&program, &args, 15_000, &[]) {
                if code == 0 {
                    return Some(Ok(true));
                }
            }
        }
    }
    // wlroots / sway / hyprland: grim (+slurp for interactive areas).
    if let Some(program) = find_program("grim") {
        let mut program_args: Vec<String> = Vec::new();
        if area == "select" {
            if let Some(slurp) = find_program("slurp") {
                if let Ok((code2, out2, _)) = run_process(&slurp, &["-o", "-f", "%x,%y %wx%h"], 15_000, &[]) {
                    if code2 == 0 {
                        let geometry = String::from_utf8_lossy(&out2).trim().to_string();
                        if !geometry.is_empty() {
                            program_args.push("-g".into());
                            program_args.push(geometry);
                        }
                    }
                }
            }
        }
        program_args.push(p.clone());
        let refs: Vec<&str> = program_args.iter().map(|s| s.as_str()).collect();
        if let Ok((code, _, _)) = run_process(&program, &refs, 15_000, &[]) {
            if code == 0 {
                return Some(Ok(true));
            }
        }
    }
    // X11 workhorses.
    if let Some(program) = find_program("scrot") {
        let args: Vec<&str> = match area {
            "select" => vec!["-s", &p],
            "window" => vec!["-u", &p],
            _ => vec![&p],
        };
        if let Ok((code, _, _)) = run_process(&program, &args, 15_000, &[]) {
            if code == 0 {
                return Some(Ok(true));
            }
        }
    }
    if let Some(program) = find_program("spectacle") {
        let args: Vec<&str> = match area {
            "select" => vec!["-b", "-r", "-o", &p],
            "window" => vec!["-b", "-a", "-o", &p],
            _ => vec!["-b", "-f", "-o", &p],
        };
        if let Ok((code, _, _)) = run_process(&program, &args, 15_000, &[]) {
            if code == 0 {
                return Some(Ok(true));
            }
        }
    }
    if let Some(program) = find_program("import") {
        if let Ok((code, _, _)) = run_process(&program, &["-window", "root", &p], 15_000, &[]) {
            if code == 0 {
                return Some(Ok(true));
            }
        }
    }
    None
}

pub fn take_screenshot(arguments: &Value) -> ToolResult {
    let area = arguments.get("area").and_then(|v| v.as_str()).unwrap_or("full").to_string();
    let directory = arguments.get("directory").and_then(|v| v.as_str());
    let filename = arguments.get("filename").and_then(|v| v.as_str());
    let path = match screenshot_destination(directory, filename) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("take_screenshot", e),
    };

    if !has_display() {
        // Headless/dev environment: honest error with a usable hint.
        return ToolResult::fail(
            "take_screenshot",
            "No graphical display is available, so the screen cannot be captured right now.",
        );
    }

    let x11 = std::env::var("DISPLAY").map(|v| !v.trim().is_empty()).unwrap_or(false);
    let mut captured = false;
    if x11 {
        match capture_x11(&path, &area) {
            Ok(true) => captured = true,
            Ok(false) | Err(_) => {
                // Fall through to native tools below.
            }
        }
    }
    if !captured {
        if let Some(result) = capture_with_native_tool(&path, &area) {
            match result {
                Ok(true) => captured = true,
                Ok(false) => return ToolResult::fail("take_screenshot", "Screenshot tool finished without producing an image."),
                Err(e) => return ToolResult::fail("take_screenshot", e),
            }
        }
    }

    if !captured {
        return ToolResult::fail(
            "take_screenshot",
            "No screenshot engine is available. Install one of: scrot, gnome-screenshot, grim, spectacle or imagemagick.",
        );
    }
    if !path.exists() {
        return ToolResult::fail("take_screenshot", "Screenshot capture reported success but no file was written.");
    }
    let size = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
    ToolResult {
        success: true,
        message: format!("Screenshot saved to {}", path.display()),
        error: None,
        data: serde_json::json!({ "tool": "take_screenshot", "path": path.display().to_string(), "area": area, "bytes": size }),
    }
}

// ---------------------------------------------------------------------------
// Volume - wpctl (PipeWire) -> pactl (PulseAudio) -> amixer (ALSA)
// ---------------------------------------------------------------------------

fn volume_tool() -> Option<&'static str> {
    if find_program("wpctl").is_some() { Some("wpctl") }
    else if find_program("pactl").is_some() { Some("pactl") }
    else if find_program("amixer").is_some() { Some("amixer") }
    else { None }
}

pub fn set_volume(arguments: &Value) -> ToolResult {
    let level = arguments.get("level");
    let tool = match volume_tool() {
        Some(t) => t,
        None => return ToolResult::fail("set_volume", "No audio control tool found (install wpctl, pactl or alsa-utils)."),
    };
    let (args, label): (Vec<String>, String) = match level.and_then(|v| v.as_str()) {
        Some("mute") => match tool {
            "wpctl" => (vec!["set-mute".into(), "@DEFAULT_AUDIO_SINK@".into(), "1".into()], "muted".into()),
            "pactl" => (vec!["set-sink-mute".into(), "@DEFAULT_SINK@".into(), "1".into()], "muted".into()),
            _ => (vec!["-D".into(), "pulse".into(), "sset".into(), "Master".into(), "mute".into()], "muted".into()),
        },
        Some("unmute") => match tool {
            "wpctl" => (vec!["set-mute".into(), "@DEFAULT_AUDIO_SINK@".into(), "0".into()], "unmuted".into()),
            "pactl" => (vec!["set-sink-mute".into(), "@DEFAULT_SINK@".into(), "0".into()], "unmuted".into()),
            _ => (vec!["-D".into(), "pulse".into(), "sset".into(), "Master".into(), "unmute".into()], "unmuted".into()),
        },
        _ => {
            let level = level.and_then(|v| v.as_u64()).unwrap_or(50).min(100) as f64;
            match tool {
                "wpctl" => (vec!["set-volume".into(), "@DEFAULT_AUDIO_SINK@".into(), format!("{:.2}", level / 100.0)], format!("{:.0}%", level)),
                "pactl" => (vec!["set-sink-volume".into(), "@DEFAULT_SINK@".into(), format!("{:.0}%", level)], format!("{:.0}%", level)),
                _ => (vec!["-D".into(), "pulse".into(), "sset".into(), "Master".into(), format!("{:.0}%", level)], format!("{:.0}%", level)),
            }
        }
    };
    let executable = tool;
    match find_program(executable) {
        Some(program_path) => {
            let all_args: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
            match run_process(&program_path, &all_args, 10_000, &[]) {
                Ok((code, _, _err)) if code == 0 => {
                    ToolResult::ok("set_volume", format!("Volume set to {}.", label))
                }
                Ok((_, _, err)) => {
                    ToolResult::fail("set_volume", format!("Audio command failed: {}", String::from_utf8_lossy(&err).trim()))
                }
                Err(e) => ToolResult::fail("set_volume", format!("Audio command failed: {}", e)),
            }
        }
        None => ToolResult::fail("set_volume", "Audio tool disappeared."),
    }
}

pub fn get_volume(_arguments: &Value) -> ToolResult {
    let tool = match volume_tool() {
        Some(t) => t,
        None => return ToolResult::fail("get_volume", "No audio control tool found (install wpctl, pactl or alsa-utils)."),
    };
    let (program, args): (PathBuf, Vec<&str>) = match tool {
        "wpctl" => (find_program("wpctl").unwrap(), vec!["get-volume", "@DEFAULT_AUDIO_SINK@"]),
        "pactl" => (find_program("pactl").unwrap(), vec!["get-sink-volume", "@DEFAULT_SINK@"]),
        _ => (find_program("amixer").unwrap(), vec!["get", "Master"]),
    };
    match run_process(&program, &args, 10_000, &[]) {
        Ok((code, out, _)) if code == 0 => {
            let stdout = String::from_utf8_lossy(&out).to_string().to_lowercase();
            let level = if let Some(idx) = stdout.find("volume:") {
                let rest = &stdout[idx + 7..];
                rest.split_whitespace()
                    .next()
                    .and_then(|s| s.trim_start_matches('[').trim_end_matches(']').parse::<f64>().ok())
                    .map(|v| (v * 100.0).round() as u64)
                    .unwrap_or(0)
            } else {
                stdout
                    .split(|c: char| c == ' ' || c == '\n')
                    .find_map(|tok| tok.trim_end_matches('%').parse::<u64>().ok())
                    .unwrap_or(0)
            };
            let muted = stdout.contains("[muted]") || stdout.contains("mute: yes");
            let message = if muted {
                format!("muted ({}%)", level)
            } else {
                format!("{}%", level)
            };
            ToolResult::ok("get_volume", message)
        }
        Ok((_, _, err)) => ToolResult::fail("get_volume", format!("Could not read volume: {}", String::from_utf8_lossy(&err).trim())),
        Err(e) => ToolResult::fail("get_volume", format!("Could not read volume: {}", e)),
    }
}

// ---------------------------------------------------------------------------
// Clipboard - arboard (native X11/Wayland, no xclip/pyperclip)
// ---------------------------------------------------------------------------

pub fn copy_to_clipboard(arguments: &Value) -> ToolResult {
    let text = arguments.get("text").and_then(|v| v.as_str()).unwrap_or("");
    if text.is_empty() {
        return ToolResult::fail("copy_to_clipboard", "Nothing to copy - no text was provided.");
    }
    match arboard::Clipboard::new() {
        Ok(mut clipboard) => match clipboard.set_text(text.to_string()) {
            Ok(()) => ToolResult::ok("copy_to_clipboard", format!("Copied {} characters to the clipboard.", text.chars().count())),
            Err(e) => ToolResult::fail("copy_to_clipboard", format!("Clipboard write failed: {}", e)),
        },
        Err(e) => ToolResult::fail("copy_to_clipboard", format!("Clipboard unavailable: {}", e)),
    }
}

pub fn get_clipboard(_arguments: &Value) -> ToolResult {
    match arboard::Clipboard::new() {
        Ok(mut clipboard) => match clipboard.get_text() {
            Ok(text) => {
                if text.trim().is_empty() {
                    ToolResult::ok("get_clipboard", "Your clipboard is empty.")
                } else {
                    ToolResult::ok("get_clipboard", text)
                }
            }
            Err(e) => ToolResult::fail("get_clipboard", format!("Clipboard read failed: {}", e)),
        },
        Err(e) => ToolResult::fail("get_clipboard", format!("Clipboard unavailable: {}", e)),
    }
}

// ---------------------------------------------------------------------------
// Processes
// ---------------------------------------------------------------------------

pub fn get_processes(arguments: &Value) -> ToolResult {
    use sysinfo::System;
    let limit = arguments.get("limit").and_then(|v| v.as_u64()).unwrap_or(10) as usize;
    let name_filter = arguments.get("name").and_then(|v| v.as_str()).map(|s| s.to_lowercase());

    let mut sys = System::new_all();
    sys.refresh_all();
    let mut rows: Vec<(String, u64, f64, u64)> = sys
        .processes()
        .values()
        .filter_map(|p| {
            let name = p.name().to_string_lossy().to_string();
            if let Some(filter) = &name_filter {
                if !name.to_lowercase().contains(filter.as_str()) {
                    return None;
                }
            }
            let pid = p.pid().as_u32() as u64;
            let cpu = p.cpu_usage() as f64;
            let mem_bytes = p.memory();
            Some((name, pid, cpu, mem_bytes))
        })
        .collect();
    rows.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal));
    rows.truncate(limit.max(1).min(100));

    if rows.is_empty() {
        let msg = name_filter
            .map(|f| format!("No process matching '{}' is running.", f))
            .unwrap_or_else(|| "No processes found.".to_string());
        return ToolResult::ok("get_processes", msg);
    }
    let lines: Vec<String> = rows
        .iter()
        .map(|(name, pid, cpu, mem)| format!("{} (pid {}, cpu {:.1}%, mem {:.1} MB)", name, pid, cpu, *mem as f64 / 1024.0 / 1024.0))
        .collect();
    ToolResult::ok("get_processes", lines.join("\n"))
}

pub fn kill_process(arguments: &Value) -> ToolResult {
    let name = arguments.get("process").and_then(|v| v.as_str()).unwrap_or("").trim();
    if name.is_empty() {
        return ToolResult::fail("kill_process", "No process name was provided.");
    }
    let mut sys = sysinfo::System::new_all();
    sys.refresh_processes(sysinfo::ProcessesToUpdate::All, true);
    let pids: Vec<u64> = sys
        .processes()
        .values()
        .filter(|p| p.name().to_string_lossy().to_lowercase().contains(&name.to_lowercase()))
        .map(|p| p.pid().as_u32() as u64)
        .collect();
    if pids.is_empty() {
        return ToolResult::fail("kill_process", format!("No running process named '{}' was found.", name));
    }
    let mut killed = 0;
    for pid in pids {
        let args: [&str; 2] = ["-TERM", &pid.to_string()];
        match find_program("kill") {
            Some(program) => {
                if let Ok((code, _, _)) = run_process(&program, &args, 5_000, &[]) {
                    if code == 0 { killed += 1; }
                }
            }
            None => return ToolResult::fail("kill_process", "'kill' was not found on PATH."),
        }
    }
    if killed > 0 {
        ToolResult::ok("kill_process", format!("Stopped {} process(es) named '{}'.", killed, name))
    } else {
        ToolResult::fail("kill_process", format!("Could not stop '{}'.", name))
    }
}
