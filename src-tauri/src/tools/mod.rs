//! PLUTO tool implementations (all real OS actions, no external AI).

pub mod apps;
pub mod files;
pub mod system;
pub mod terminal;
pub mod voice;

use serde_json::{json, Value};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct ToolResult {
    pub success: bool,
    pub message: String,
    pub error: Option<String>,
    pub data: Value,
}

impl ToolResult {
    pub fn ok(tool: &str, message: impl Into<String>) -> Self {
        ToolResult { success: true, message: message.into(), error: None, data: json!({ "tool": tool }) }
    }

    pub fn fail(tool: &str, message: impl Into<String>) -> Self {
        let message = message.into();
        ToolResult {
            success: false,
            message: message.clone(),
            error: Some(message),
            data: json!({ "tool": tool, "success": false }),
        }
    }
}

/// True when a graphical session (X11 or Wayland) is available.
pub fn has_display() -> bool {
    let display = std::env::var("DISPLAY").unwrap_or_default();
    let wayland = std::env::var("WAYLAND_DISPLAY").unwrap_or_default();
    !display.is_empty() || !wayland.is_empty()
}

/// Expand `~` and resolve to an absolute path, validating that the target
/// stays inside the user's home directory (the PLUTO sandbox).
pub fn validate_path(raw: &str) -> Result<PathBuf, String> {
    let expanded = crate::nlu::expand_home(raw.trim());
    if expanded.trim().is_empty() {
        return Err("Empty path".into());
    }
    let p = Path::new(&expanded);
    // Reject explicit traversal before touching the filesystem.
    if p.components().any(|c| matches!(c, std::path::Component::ParentDir)) {
        return Err("Path traversal is not allowed".into());
    }

    let abs = if p.exists() {
        p.canonicalize().map_err(|e| format!("Cannot resolve path: {}", e))?
    } else {
        // New target: canonicalize the deepest existing ancestor.
        let mut ancestor = p.to_path_buf();
        while !ancestor.exists() {
            if !ancestor.pop() {
                return Err(format!("Cannot resolve path: {}", raw));
            }
        }
        let canon = ancestor.canonicalize().map_err(|e| format!("Cannot resolve path: {}", e))?;
        let tail = p.strip_prefix(&ancestor).unwrap_or(p);
        canon.join(tail)
    };

    let home = dirs::home_dir().ok_or_else(|| "Cannot determine home directory".to_string())?;
    let home = home.canonicalize().unwrap_or(home);
    if !abs.starts_with(&home) {
        // Screenshots/temp may live under /tmp temporarily; everything else is home-scoped.
        let in_tmp = abs.starts_with(std::env::temp_dir());
        if !in_tmp {
            return Err(format!("Path is outside the allowed sandbox (home): {}", abs.display()));
        }
    }
    Ok(abs)
}

/// Validate a path as an existing file.
pub fn validate_existing_file(raw: &str) -> Result<PathBuf, String> {
    let abs = validate_path(raw)?;
    if !abs.is_file() {
        return Err(format!("File not found: {}", abs.display()));
    }
    Ok(abs)
}

/// Validate a path as an existing directory.
pub fn validate_existing_dir(raw: &str) -> Result<PathBuf, String> {
    let abs = validate_path(raw)?;
    if !abs.is_dir() {
        return Err(format!("Directory not found: {}", abs.display()));
    }
    Ok(abs)
}

/// Locate an executable on PATH.
pub fn find_program(name: &str) -> Option<PathBuf> {
    which::which(name).ok()
}

/// Run a command and wait for it with an optional timeout (milliseconds).
/// Output is captured through reader threads so pipes never deadlock.
pub fn run_process(
    program: &Path,
    args: &[&str],
    timeout_ms: u64,
    env: &[(&str, &str)],
) -> std::io::Result<(i32, Vec<u8>, Vec<u8>)> {
    use std::io::Read;
    use std::process::Stdio;

    let mut cmd = std::process::Command::new(program);
    cmd.args(args).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    for (k, v) in env {
        cmd.env(k, v);
    }
    let mut child = cmd.spawn()?;
    let mut stdout = child.stdout.take().map(|s| std::thread::spawn(move || {
        let mut buf = Vec::new();
        let mut handle = s;
        let _ = handle.read_to_end(&mut buf);
        buf
    }));
    let mut stderr = child.stderr.take().map(|s| std::thread::spawn(move || {
        let mut buf = Vec::new();
        let mut handle = s;
        let _ = handle.read_to_end(&mut buf);
        buf
    }));

    let start = std::time::Instant::now();
    let mut status = None;
    loop {
        match child.try_wait() {
            Ok(Some(s)) => {
                status = Some(s);
                break;
            }
            _ => {
                if start.elapsed().as_millis() as u64 >= timeout_ms {
                    let _ = child.kill();
                    let _ = child.wait();
                    status = None;
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(40));
            }
        }
    }

    let out = stdout.take().and_then(|h| h.join().ok()).unwrap_or_default();
    let err = stderr.take().and_then(|h| h.join().ok()).unwrap_or_default();
    let code = if let Some(s) = status {
        s.code().unwrap_or(-1)
    } else {
        -1
    };
    Ok((code, out, err))
}

/// Convenience: run an executable with args (no shell).
pub fn run_tool_exe(
    tool: &str,
    args: &[&str],
    timeout_ms: u64,
    env: &[(&str, &str)],
) -> ToolResult {
    match find_program(args[0]) {
        None => ToolResult::fail(tool, format!("'{}' is not installed on this system", args[0])),
        Some(program) => match run_process(&program, &args[1..], timeout_ms, env) {
            Ok((code, out, err)) => {
                let message = String::from_utf8_lossy(&out).trim().to_string();
                if code == 0 {
                    ToolResult { success: true, message, error: None, data: json!({ "tool": tool, "exit_code": code }) }
                } else {
                    let errmsg = String::from_utf8_lossy(&err).trim().to_string();
                    ToolResult::fail(tool, format!("{} failed (exit {}): {}", tool, code, if errmsg.is_empty() { message } else { errmsg }))
                }
            }
            Err(e) => ToolResult::fail(tool, format!("Failed to run {}: {}", tool, e)),
        },
    }
}

/// Dispatch a planned tool by name. Runs inside a blocking task by the
/// orchestrator; everything that touches the OS is real Rust/Tauri code.
pub async fn run_tool(name: &str, arguments: &Value) -> ToolResult {
    let name = name.to_string();
    let arguments = arguments.clone();
    let fail_name = name.clone();
    tauri::async_runtime::spawn_blocking(move || {
        match name.as_str() {
            // system
            "take_screenshot" => system::take_screenshot(&arguments),
            "set_volume" => system::set_volume(&arguments),
            "get_volume" => system::get_volume(&arguments),
            "copy_to_clipboard" => system::copy_to_clipboard(&arguments),
            "get_clipboard" => system::get_clipboard(&arguments),
            "get_processes" => system::get_processes(&arguments),
            "kill_process" => system::kill_process(&arguments),
            // files
            "open_file" => files::open_file(&arguments),
            "open_folder" => files::open_folder(&arguments),
            "find_files" => files::find_files(&arguments),
            "create_folder" => files::create_folder(&arguments),
            "create_file" => files::create_file(&arguments),
            "read_file" => files::read_file(&arguments),
            "list_directory" => files::list_directory(&arguments),
            "delete_file" => files::delete_file(&arguments),
            "move_file" => files::move_file(&arguments),
            "copy_file" => files::copy_file(&arguments),
            // apps + browser
            "open_browser" => apps::open_browser(),
            "open_application" => apps::open_application(&arguments),
            "close_application" => apps::close_application(&arguments),
            "switch_to_application" => apps::switch_to_application(&arguments),
            "list_running_applications" => apps::list_running_applications(),
            "open_url" => apps::open_url(&arguments),
            "browser_search" => apps::browser_search(&arguments),
            "browser_click" => apps::browser_click(&arguments),
            "browser_key" => apps::browser_key(&arguments),
            "browser_snapshot" => apps::browser_snapshot(&arguments),
            "close_browser" => apps::close_browser(),
            "send_message" => apps::send_message(&arguments),
            "open_chat_app" => apps::open_chat_app(&arguments),
            // terminal
            "execute_command" => terminal::execute_command(&arguments),
            _ => ToolResult::fail(&name, format!("Unknown tool: {}", name)),
        }
    })
    .await
    .unwrap_or_else(|e| ToolResult::fail(&fail_name, format!("Tool task panicked: {}", e)))
}
