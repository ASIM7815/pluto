//! Safe terminal execution.
//!
//! Security model:
//!   BLOCKED           -> never executed (destructive patterns)
//!   SAFE              -> executed directly as argv (no shell)
//!   CONFIRM_REQUIRED  -> the orchestrator asks the user first, then runs
//!                         with a bounded timeout; shell metacharacters are
//!                         only interpreted after explicit approval.

use super::{find_program, ToolResult};
use serde_json::Value;
use std::path::PathBuf;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CommandSafety {
    Safe,
    ConfirmRequired,
    Blocked,
}

pub fn classify_command(command: &str) -> CommandSafety {
    let lower = command.trim().to_lowercase();
    let blocked = [
        r"rm\s+-rf\s+/",
        r"dd\s+if=",
        r":\(\)\{.*\};:",
        r"mkfs\.",
        r"sudo\s+rm",
        r"chmod\s+777",
        r">/dev/sd",
        r"shutdown\s+-h\s+now",
        r"reboot\s+--force",
    ];
    for pattern in blocked {
        if regex::Regex::new(pattern).map(|r| r.is_match(&lower)).unwrap_or(false) {
            return CommandSafety::Blocked;
        }
    }
    let dangerous = [
        "rm ", "delete", "format", "mkfs", "fdisk", "shutdown", "reboot", "poweroff",
        "kill -9", "killall", "iptables", "ufw disable", "sudo ", "su ", "passwd",
        "chmod", "chown", "dd ", ">", ">>", "<", "|", "&", ";", "`", "$(", "rm -rf",
    ];
    if dangerous.iter().any(|k| lower.contains(k)) {
        return CommandSafety::ConfirmRequired;
    }
    CommandSafety::Safe
}

/// Minimal shell-like tokenizer (quotes + escapes). Used for SAFE commands so
/// we never run a shell for them.
fn tokenize(command: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut quote: Option<char> = None;
    let mut chars = command.chars().peekable();
    while let Some(c) = chars.next() {
        match quote {
            Some(q) => {
                if c == q {
                    quote = None;
                } else {
                    current.push(c);
                }
            }
            None => match c {
                '\'' | '"' => quote = Some(c),
                '\\' => {
                    if let Some(next) = chars.next() {
                        current.push(next);
                    }
                }
                ' ' | '\t' | '\n' => {
                    if !current.is_empty() {
                        tokens.push(std::mem::take(&mut current));
                    }
                }
                _ => current.push(c),
            },
        }
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    tokens
}

pub fn execute_argv(command: &str, cwd: Option<&str>, timeout_ms: u64) -> Result<(i32, Vec<u8>, Vec<u8>), String> {
    let tokens = tokenize(command);
    if tokens.is_empty() {
        return Err("Empty command".into());
    }
    let program = find_program(&tokens[0]).ok_or_else(|| format!("Command '{}' not found on PATH.", tokens[0]))?;
    let args: Vec<&str> = tokens[1..].iter().map(|s| s.as_str()).collect();
    let env: Vec<(&str, &str)> = Vec::new();
    if let Some(dir) = cwd {
        if !PathBuf::from(dir).is_dir() {
            return Err(format!("Working directory not found: {}", dir));
        }
    }
    run_process_with_cwd(&program, &args, cwd, timeout_ms, &env)
}

/// Same as `run_process` but with a working directory.
fn run_process_with_cwd(
    program: &std::path::Path,
    args: &[&str],
    cwd: Option<&str>,
    timeout_ms: u64,
    env: &[(&str, &str)],
) -> Result<(i32, Vec<u8>, Vec<u8>), String> {
    use std::io::Read;
    use std::process::Stdio;
    let mut cmd = std::process::Command::new(program);
    cmd.args(args).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    if let Some(d) = cwd {
        cmd.current_dir(d);
    }
    for (k, v) in env {
        cmd.env(k, v);
    }
    let mut child = cmd.spawn().map_err(|e| format!("Failed to run command: {}", e))?;
    let out_thread = child.stdout.take().map(|mut s| {
        std::thread::spawn(move || {
            let mut buf = Vec::new();
            let _ = s.read_to_end(&mut buf);
            buf
        })
    });
    let err_thread = child.stderr.take().map(|mut s| {
        std::thread::spawn(move || {
            let mut buf = Vec::new();
            let _ = s.read_to_end(&mut buf);
            buf
        })
    });
    let start = std::time::Instant::now();
    let status = loop {
        match child.try_wait() {
            Ok(Some(s)) => break Some(s),
            _ => {
                if start.elapsed().as_millis() as u64 >= timeout_ms {
                    let _ = child.kill();
                    let _ = child.wait();
                    break None;
                }
                std::thread::sleep(std::time::Duration::from_millis(40));
            }
        }
    };
    let out = out_thread.and_then(|h| h.join().ok()).unwrap_or_default();
    let err = err_thread.and_then(|h| h.join().ok()).unwrap_or_default();
    let code = status.map(|s| s.code().unwrap_or(-1)).unwrap_or(-1);
    Ok((code, out, err))
}

pub fn execute_command(arguments: &Value) -> ToolResult {
    let command = arguments.get("command").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
    if command.is_empty() {
        return ToolResult::fail("execute_command", "No command was provided.");
    }
    let cwd = arguments.get("working_directory").and_then(|v| v.as_str()).map(|s| s.to_string());
    let safety = classify_command(&command);
    if safety == CommandSafety::Blocked {
        return ToolResult::fail("execute_command", "That command is blocked by PLUTO's security policy.");
    }
    // The orchestrator has already applied the confirmation gate for
    // CONFIRM_REQUIRED commands before invoking us.
    let has_shell_meta = regex::Regex::new(r"[;&|`$><]").unwrap().is_match(&command);
    let (code, out, err) = if has_shell_meta {
        // Explicitly approved shell command: bounded, `/bin/sh`.
        match find_program("sh") {
            Some(sh) => match run_process_with_cwd(&sh, &["-c", &command], cwd.as_deref(), 45_000, &[]) {
                Ok(result) => result,
                Err(e) => return ToolResult::fail("execute_command", e),
            },
            None => return ToolResult::fail("execute_command", "/bin/sh not found."),
        }
    } else {
        match execute_argv(&command, cwd.as_deref(), 30_000) {
            Ok(r) => r,
            Err(e) => return ToolResult::fail("execute_command", e),
        }
    };

    let stdout = String::from_utf8_lossy(&out).to_string();
    let stderr = String::from_utf8_lossy(&err).to_string();
    if code == 0 {
        let message = if stdout.is_empty() {
            "Command finished successfully.".to_string()
        } else {
            format!("Command finished (exit 0). Output: {}", stdout.chars().take(400).collect::<String>())
        };
        ToolResult {
            success: true,
            message,
            error: None,
            data: serde_json::json!({ "tool": "execute_command", "command": command, "returncode": code, "stdout": stdout, "stderr": stderr }),
        }
    } else {
        let detail = if stderr.is_empty() { stdout } else { stderr };
        ToolResult::fail("execute_command", format!("Command exited with code {}: {}", code, detail.chars().take(300).collect::<String>()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blocks_destructive_patterns() {
        assert_eq!(classify_command("rm -rf /"), CommandSafety::Blocked);
        assert_eq!(classify_command("dd if=/dev/zero of=/dev/sda"), CommandSafety::Blocked);
        assert_eq!(classify_command("sudo rm -rf /home/user"), CommandSafety::Blocked);
    }

    #[test]
    fn confirms_dangerous_commands() {
        assert_eq!(classify_command("rm -rf ../temp"), CommandSafety::ConfirmRequired);
        assert_eq!(classify_command("killall firefox"), CommandSafety::ConfirmRequired);
        assert_eq!(classify_command("ls -la; rm /tmp/x"), CommandSafety::ConfirmRequired);
    }

    #[test]
    fn safe_commands() {
        assert_eq!(classify_command("ls -la /home/user"), CommandSafety::Safe);
        assert_eq!(classify_command("uname -a"), CommandSafety::Safe);
    }

    #[test]
    fn tokenizes_quotes() {
        assert_eq!(tokenize("echo 'hello world'"), vec!["echo", "hello world"]);
        assert_eq!(tokenize("ls -la"), vec!["ls", "-la"]);
    }
}
