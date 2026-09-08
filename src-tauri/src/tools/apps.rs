//! Application launching/management, browser control and messaging tools.

use super::{find_program, has_display, run_process, ToolResult};
use serde_json::Value;
use std::path::PathBuf;

use crate::nlu::{app_alias, expand_home};

const TERMINAL_PROGRAMS: &[&str] = &["vim", "emacs", "htop", "top", "git", "bash", "zsh"];

fn is_process_running(name: &str) -> bool {
    let mut sys = sysinfo::System::new_all();
    sys.refresh_processes(sysinfo::ProcessesToUpdate::All, true);
    sys.processes()
        .values()
        .any(|p| p.name().to_string_lossy().to_lowercase() == name.to_lowercase())
}

fn spawn_detached(program: &PathBuf, args: &[&str]) -> Result<std::process::Child, String> {
    use std::os::unix::process::CommandExt;
    let mut cmd = std::process::Command::new(program);
    cmd.args(args);
    cmd.stdin(std::process::Stdio::null());
    cmd.stdout(std::process::Stdio::null());
    cmd.stderr(std::process::Stdio::null());
    cmd.process_group(0); // detach from PLUTO's process group
    cmd.spawn().map_err(|e| format!("Failed to launch: {}", e))
}

pub fn resolve_app(application: &str) -> String {
    app_alias(application)
        .map(|exe| exe.split_whitespace().next().unwrap_or("").to_string())
        .filter(|e| !e.is_empty())
        .unwrap_or_else(|| application.trim().split_whitespace().next().unwrap_or("").to_string())
}

// ---------------------------------------------------------------------------
// Browser launching (never fails silently)
// ---------------------------------------------------------------------------

/// Common Linux browser executables, most-likely first.
const BROWSER_CANDIDATES: &[&str] = &[
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "brave-browser",
    "microsoft-edge",
    "microsoft-edge-stable",
    "firefox",
    "firefox-esr",
    "epiphany",
    "falkon",
    "vivaldi-stable",
    "opera",
    "qutebrowser",
];

fn default_browser_binary() -> Option<PathBuf> {
    // 1) $BROWSER (xdg convention, colon separated).
    if let Ok(browser) = std::env::var("BROWSER") {
        for candidate in browser.split(':') {
            let candidate = candidate.trim();
            if !candidate.is_empty() {
                if let Some(p) = find_program(candidate) {
                    return Some(p);
                }
            }
        }
    }
    // 2) xdg-settings reports the user's configured default (.desktop id).
    if let Some(settings) = find_program("xdg-settings") {
        if let Ok((code, out, _)) = run_process(&settings, &["get", "default-web-browser"], 5_000, &[]) {
            if code == 0 {
                let desktop = String::from_utf8_lossy(&out).trim().to_lowercase();
                let name = desktop.trim_end_matches(".desktop").to_string();
                if !name.is_empty() {
                    for candidate in BROWSER_CANDIDATES.iter().copied() {
                        if name == candidate || name.starts_with(candidate) || candidate.starts_with(&name) {
                            if let Some(p) = find_program(candidate) {
                                return Some(p);
                            }
                        }
                    }
                }
            }
        }
    }
    // 3) Any installed common browser as a last resort.
    for candidate in BROWSER_CANDIDATES.iter().copied() {
        if let Some(p) = find_program(candidate) {
            return Some(p);
        }
    }
    None
}

/// Open the user's *default* browser (does not assume Firefox/Chrome).
pub fn open_browser() -> ToolResult {
    if !has_display() {
        return ToolResult::fail(
            "open_browser",
            "I can't open a browser right now: no graphical display session is available.",
        );
    }
    let program = match default_browser_binary() {
        Some(p) => p,
        None => {
            return ToolResult::fail(
                "open_browser",
                "I couldn't open the browser because no default browser is configured and no common browser \
                 (Chrome, Chromium, Firefox, Brave...) is installed. Install one, or run \
                 'xdg-settings set default-web-browser <browser>.desktop'.",
            )
        }
    };
    let name = program
        .file_name()
        .map(|f| f.to_string_lossy().to_string())
        .unwrap_or_else(|| "browser".to_string());
    match spawn_detached(&program, &["about:blank"]) {
        Ok(mut child) => {
            std::thread::sleep(std::time::Duration::from_millis(700));
            // Browsers often run under a shorter process name ("chrome" for
            // google-chrome) or hand off to an already-running instance.
            let running = is_process_running(&name)
                || ["google-chrome", "chrome", "chromium", "chromium-browser", "firefox", "brave-browser", "microsoft-edge"]
                    .iter()
                    .any(|b| is_process_running(b));
            std::thread::spawn(move || {
                let _ = child.wait();
            });
            if running {
                ToolResult::ok("open_browser", format!("Opened your default browser ({}).", name))
            } else {
                ToolResult::fail(
                    "open_browser",
                    format!("I launched {} but it did not start. Check the browser installation.", name),
                )
            }
        }
        Err(e) => ToolResult::fail("open_browser", format!("I couldn't open the browser: {}", e)),
    }
}

pub fn open_url(arguments: &Value) -> ToolResult {
    let url = arguments.get("url").and_then(|v| v.as_str()).unwrap_or("").trim();
    if url.is_empty() {
        return ToolResult::fail("open_url", "No URL was provided.");
    }
    if !has_display() {
        return ToolResult::fail(
            "open_url",
            format!("I can't open {} right now: no graphical display session is available.", url),
        );
    }
    let has_xdg = find_program("xdg-open").is_some();
    match find_program("xdg-open").or_else(|| find_program("gio")).or_else(|| find_program("exo-open")) {
        Some(program) => {
            let mut args: Vec<&str> = Vec::new();
            let tool_name = program.file_name().and_then(|f| f.to_str()).unwrap_or("");
            if tool_name == "gio" {
                args.push("open");
            }
            args.push(url);
            match run_process(&program, &args, 10_000, &[]) {
                Ok((code, _, _err)) if code == 0 => ToolResult::ok("open_url", format!("Opened {} in your default browser.", url)),
                Ok((_, _, err)) => {
                    let stderr = String::from_utf8_lossy(&err).trim().to_string();
                    let detail = if stderr.is_empty() { "the opener reported an error".to_string() } else { stderr };
                    let mut message = format!("I couldn't open {}: {}", url, detail.chars().take(200).collect::<String>());
                    if has_xdg && default_browser_binary().is_none() {
                        message.push_str(" No default browser appears to be configured - install one or run 'xdg-settings set default-web-browser <browser>.desktop'.");
                    }
                    ToolResult::fail("open_url", message)
                }
                Err(e) => {
                    let mut message = format!("I couldn't open {}: {}", url, e);
                    if default_browser_binary().is_none() {
                        message.push_str(" No default browser appears to be configured.");
                    }
                    ToolResult::fail("open_url", message)
                }
            }
        }
        None => {
            let mut message = "No desktop opener is installed (xdg-open / gio). Install xdg-utils.".to_string();
            if default_browser_binary().is_some() {
                message.push_str(" PLUTO found a browser binary; install xdg-utils so URLs can be handed to it.");
            }
            ToolResult::fail("open_url", message)
        }
    }
}

pub fn browser_search(arguments: &Value) -> ToolResult {
    let query = arguments.get("query").and_then(|v| v.as_str()).unwrap_or("").trim();
    let site = arguments.get("site").and_then(|v| v.as_str()).unwrap_or("");
    let url_override = arguments.get("url").and_then(|v| v.as_str()).unwrap_or("");
    if query.is_empty() {
        return ToolResult::fail("browser_search", "No search query was provided.");
    }
    let encoded: String = query
        .chars()
        .map(|c| match c {
            ' ' => "+".to_string(),
            _ => c.to_string(),
        })
        .collect();
    let url = if !url_override.is_empty() {
        url_override.to_string()
    } else {
        let base = match site {
            "youtube" => "https://www.youtube.com/results",
            "duckduckgo" => "https://duckduckgo.com",
            "bing" => "https://www.bing.com/search",
            "github" => "https://github.com/search",
            "reddit" => "https://www.reddit.com/search",
            "wikipedia" => "https://en.wikipedia.org/w/index.php",
            _ => "https://www.google.com/search",
        };
        if site == "wikipedia" {
            format!("{}?search={}", base, encoded)
        } else {
            format!("{}?q={}", base, encoded)
        }
    };
    open_url(&serde_json::json!({ "url": url }))
}

pub fn browser_key(arguments: &Value) -> ToolResult {
    let key = arguments.get("key").and_then(|v| v.as_str()).unwrap_or("F5");
    match find_program("xdotool") {
        Some(program) => {
            let args = ["key", "--clearmodifiers", key];
            match run_process(&program, &args, 8_000, &[]) {
                Ok((code, _, _)) if code == 0 => ToolResult::ok("browser_key", format!("Sent key '{}' to the active window.", key)),
                Ok(_) => ToolResult::fail("browser_key", format!("Could not send key '{}' (no active browser window?).", key)),
                Err(e) => ToolResult::fail("browser_key", format!("xdotool failed: {}", e)),
            }
        }
        None => ToolResult::fail("browser_key", "xdotool is not installed - keyboard control needs X11/xdotool."),
    }
}

pub fn browser_click(arguments: &Value) -> ToolResult {
    let index = arguments.get("index").and_then(|v| v.as_u64()).unwrap_or(0);
    // Focus the user's browser so they see the page, then report. Full
    // in-page DOM clicking is provided by the browser itself; we never inject
    // into an untrusted page without user interaction.
    if let Some(program) = find_program("wmctrl") {
        for window_class in ["google-chrome", "chromium", "firefox", "brave-browser"] {
            if let Ok((code, _, _)) = run_process(&program, &["-a", window_class], 5_000, &[]) {
                if code == 0 {
                    return ToolResult::ok("browser_click", format!("Brought your browser to the front (result #{} ready to open).", index + 1));
                }
            }
        }
    }
    ToolResult::fail(
        "browser_click",
        "I cannot click inside the page without an accessibility/automation bridge. I focused the browser when possible - click the result yourself, or use the browser's search flow.",
    )
}

pub fn close_browser() -> ToolResult {
    for name in ["google-chrome", "chromium", "firefox", "brave-browser", "microsoft-edge"] {
        if let Some(program) = find_program("pkill") {
            if is_process_running(name) {
                if let Ok((code, _, _)) = run_process(&program, &["-x", name], 5_000, &[]) {
                    if code == 0 {
                        return ToolResult::ok("close_browser", format!("Closed {} browser.", name));
                    }
                }
            }
        } else {
            return ToolResult::fail("close_browser", "pkill is not available.");
        }
    }
    ToolResult::ok("close_browser", "No supported browser process was running.")
}

pub fn browser_snapshot(_arguments: &Value) -> ToolResult {
    let dir = expand_home("~/Pictures");
    super::system::take_screenshot(&serde_json::json!({ "area": "window", "directory": dir }))
}

// ---------------------------------------------------------------------------
// Applications
// ---------------------------------------------------------------------------

pub fn open_application(arguments: &Value) -> ToolResult {
    let application = arguments.get("application").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
    let extra: Vec<String> = arguments
        .get("arguments")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect())
        .unwrap_or_default();
    if application.is_empty() {
        return ToolResult::fail("open_application", "No application name was provided.");
    }
    let executable = resolve_app(&application);
    if executable.contains('.') && !executable.contains('/') && !executable.is_empty() {
        // Looks like a website - open in the browser instead.
        return open_url(&serde_json::json!({ "url": format!("https://{}", executable) }));
    }
    let program = match find_program(&executable) {
        Some(p) => p,
        None => {
            return ToolResult::fail(
                "open_application",
                format!("'{}' does not appear to be installed (no '{}' on PATH).", application, executable),
            );
        }
    };
    if !TERMINAL_PROGRAMS.contains(&executable.as_str()) && !has_display() {
        return ToolResult::fail("open_application", format!("I can't open {} right now: no graphical display session is available.", application));
    }
    if is_process_running(&executable) {
        return ToolResult::ok("open_application", format!("{} is already running.", application));
    }
    let arg_refs: Vec<&str> = extra.iter().map(|s| s.as_str()).collect();
    match spawn_detached(&program, &arg_refs) {
        Ok(mut child) => {
            // Give the process a moment, then verify + reap in a thread.
            std::thread::sleep(std::time::Duration::from_millis(900));
            let started = is_process_running(&executable);
            std::thread::spawn(move || {
                let _ = child.wait();
            });
            if started {
                ToolResult::ok("open_application", format!("Opened {}.", application))
            } else {
                ToolResult::fail(
                    "open_application",
                    format!("I tried to open {} but the process did not start. Is it installed and working?", application),
                )
            }
        }
        Err(e) => ToolResult::fail("open_application", e),
    }
}

pub fn close_application(arguments: &Value) -> ToolResult {
    let application = arguments.get("application").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
    if application.is_empty() {
        return ToolResult::fail("close_application", "No application name was provided.");
    }
    let executable = resolve_app(&application);
    if let Some(program) = find_program("wmctrl") {
        if let Ok((code, _, _)) = run_process(&program, &["-c", &application], 5_000, &[]) {
            if code == 0 {
                return ToolResult::ok("close_application", format!("Closed {}.", application));
            }
        }
    }
    if let Some(program) = find_program("pkill") {
        if let Ok((code, _, _)) = run_process(&program, &["-x", &executable], 5_000, &[]) {
            if code == 0 {
                return ToolResult::ok("close_application", format!("Closed {}.", application));
            }
        }
        return ToolResult::fail("close_application", format!("Could not close {} - is it running?", application));
    }
    ToolResult::fail("close_application", "No process control tool is available (wmctrl / pkill).")
}

pub fn switch_to_application(arguments: &Value) -> ToolResult {
    let application = arguments.get("application").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
    match find_program("wmctrl") {
        Some(program) => match run_process(&program, &["-a", &application], 5_000, &[]) {
            Ok((code, _, _)) if code == 0 => ToolResult::ok("switch_to_application", format!("Switched to {}.", application)),
            Ok(_) => ToolResult::fail("switch_to_application", format!("Could not find a window for '{}'.", application)),
            Err(e) => ToolResult::fail("switch_to_application", format!("wmctrl failed: {}", e)),
        },
        None => ToolResult::fail("switch_to_application", "wmctrl is not installed - window switching needs wmctrl (X11)."),
    }
}

pub fn list_running_applications() -> ToolResult {
    let mut sys = sysinfo::System::new_all();
    sys.refresh_processes(sysinfo::ProcessesToUpdate::All, true);
    let mut names: Vec<(String, f64)> = sys
        .processes()
        .values()
        .map(|p| (p.name().to_string_lossy().to_string(), p.cpu_usage() as f64))
        .collect();
    names.retain(|(n, _)| !n.is_empty() && n.len() > 1);
    names.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    names.dedup_by(|a, b| a.0 == b.0);
    names.truncate(25);
    let message = names
        .iter()
        .map(|(n, _)| n.as_str())
        .collect::<Vec<_>>()
        .join(", ");
    if message.is_empty() {
        return ToolResult::ok("list_running_applications", "No applications detected.");
    }
    ToolResult::ok("list_running_applications", message)
}

// ---------------------------------------------------------------------------
// Messaging (opens the chat service; message text is prepared/composed)
// ---------------------------------------------------------------------------

fn chat_web_url(app: &str, message: Option<&str>) -> String {
    let encoded = message.map(|m| {
        m.chars()
            .map(|c| match c {
                ' ' => "+".to_string(),
                '&' => "%26".to_string(),
                '?' => "%3F".to_string(),
                '#' => "%23".to_string(),
                _ => c.to_string(),
            })
            .collect::<String>()
    });
    match app {
        "telegram" => "https://web.telegram.org".to_string(),
        "signal" => "https://signal.org".to_string(),
        _ => {
            if let Some(text) = encoded {
                format!("https://web.whatsapp.com/send?text={}", text)
            } else {
                "https://web.whatsapp.com".to_string()
            }
        }
    }
}

pub fn open_chat_app(arguments: &Value) -> ToolResult {
    let app = arguments.get("app").and_then(|v| v.as_str()).unwrap_or("whatsapp").to_lowercase();
    let url = chat_web_url(&app, None);
    let result = open_url(&serde_json::json!({ "url": url }));
    if result.success {
        ToolResult::ok("open_chat_app", format!("Opened {} web.", app))
    } else {
        result
    }
}

pub fn send_message(arguments: &Value) -> ToolResult {
    let app = arguments.get("app").and_then(|v| v.as_str()).unwrap_or("whatsapp").to_lowercase();
    let recipient = arguments.get("recipient").and_then(|v| v.as_str()).unwrap_or("").trim();
    let message = arguments.get("message").and_then(|v| v.as_str()).unwrap_or("").trim();
    if message.is_empty() {
        return ToolResult::fail("send_message", "No message content was provided.");
    }
    let url = chat_web_url(&app, Some(message));
    let result = open_url(&serde_json::json!({ "url": url }));
    if result.success {
        let who = if recipient.is_empty() { "the selected contact".to_string() } else { recipient.to_string() };
        ToolResult::ok(
            "send_message",
            format!(
                "Opened {} web with your message prepared for {}: \"{}\". Press send in the chat window to deliver it (PLUTO never sends without your visible confirmation).",
                app, who, message
            ),
        )
    } else {
        result
    }
}
