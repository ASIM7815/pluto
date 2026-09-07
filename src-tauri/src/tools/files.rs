//! File tools: open, find, create, read, list, delete, move, copy.
//! All paths pass through `validate_path` (home-sandboxed).

use super::{find_program, run_process, validate_path, ToolResult};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

const MAX_READ_CHARS: usize = 16_384;
const MAX_LIST_ITEMS: usize = 500;
const MAX_FIND_RESULTS: usize = 25;

fn opener() -> Option<PathBuf> {
    find_program("xdg-open")
        .or_else(|| find_program("gio"))
        .or_else(|| find_program("exo-open"))
}

fn open_with_default(target: &Path) -> ToolResult {
    let tool_name = "open_file";
    let args: Vec<String> = vec![target.display().to_string()];
    let opener_name = opener();
    if let Some(program) = opener_name {
        let refs: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
        if let Ok((code, _, err)) = run_process(&program, &refs, 10_000, &[]) {
            if code == 0 {
                return ToolResult::ok(tool_name, format!("Opened {} with its default application.", target.display()));
            }
            return ToolResult::fail(tool_name, format!("Could not open {}: {}", target.display(), String::from_utf8_lossy(&err).trim()));
        }
        return ToolResult::fail(tool_name, "Could not launch the default opener.");
    }
    ToolResult::fail(tool_name, "No desktop opener is installed (tried xdg-open, gio, exo-open).")
}

pub fn open_file(arguments: &Value) -> ToolResult {
    let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("");
    let abs = match super::validate_existing_file(path) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("open_file", e),
    };
    open_with_default(&abs)
}

pub fn open_folder(arguments: &Value) -> ToolResult {
    let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("~");
    let abs = match super::validate_existing_dir(path) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("open_folder", e),
    };
    open_with_default(&abs)
}

pub fn find_files(arguments: &Value) -> ToolResult {
    let query = arguments.get("query").and_then(|v| v.as_str()).unwrap_or("").to_lowercase();
    if query.is_empty() {
        return ToolResult::fail("find_files", "No search query was provided.");
    }
    let location = arguments.get("location").and_then(|v| v.as_str()).unwrap_or("~");
    let root = match super::validate_existing_dir(location) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("find_files", e),
    };
    let max_results = arguments.get("max_results").and_then(|v| v.as_u64()).unwrap_or(25) as usize;
    let max_results = max_results.clamp(1, 100);

    let mut matches: Vec<(PathBuf, String)> = Vec::new();
    let skip = ["node_modules", "venv", ".git", "__pycache__", "target"];
    for entry in walkdir::WalkDir::new(&root)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| !skip.contains(&e.file_name().to_string_lossy().as_ref()))
        .filter_map(|e| e.ok())
    {
        if entry.path().is_dir() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().to_string();
        if name.to_lowercase().contains(&query) {
            matches.push((entry.path().to_path_buf(), name));
            if matches.len() >= max_results {
                break;
            }
        }
    }

    if matches.is_empty() {
        return ToolResult::ok("find_files", format!("No files found matching '{}' in {}.", query, root.display()));
    }
    let preview: Vec<String> = matches.iter().take(10).map(|(p, _)| format!("- {}", p.display())).collect();
    let more = if matches.len() > 10 { format!("\n... and {} more", matches.len() - 10) } else { String::new() };
    let files: Vec<serde_json::Value> = matches
        .iter()
        .map(|(p, name)| serde_json::json!({ "path": p.display().to_string(), "name": name }))
        .collect();
    ToolResult {
        success: true,
        message: format!("Found {} file(s) matching '{}':\n{}{}", matches.len(), query, preview.join("\n"), more),
        error: None,
        data: serde_json::json!({ "tool": "find_files", "files": files, "count": matches.len() }),
    }
}

pub fn create_folder(arguments: &Value) -> ToolResult {
    let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("");
    let abs = match validate_path(path) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("create_folder", e),
    };
    if abs.exists() {
        return ToolResult::ok("create_folder", format!("Folder already exists: {}", abs.display()));
    }
    if let Err(e) = fs::create_dir_all(&abs) {
        return ToolResult::fail("create_folder", format!("Failed to create folder: {}", e));
    }
    ToolResult::ok("create_folder", format!("Created folder {}", abs.display()))
}

pub fn create_file(arguments: &Value) -> ToolResult {
    let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("");
    let content = arguments.get("content").and_then(|v| v.as_str()).unwrap_or("");
    let abs = match validate_path(path) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("create_file", e),
    };
    if let Some(parent) = abs.parent() {
        if let Err(e) = fs::create_dir_all(parent) {
            return ToolResult::fail("create_file", format!("Failed to create parent folder: {}", e));
        }
    }
    if let Err(e) = fs::write(&abs, content.as_bytes()) {
        return ToolResult::fail("create_file", format!("Failed to create file: {}", e));
    }
    ToolResult::ok("create_file", format!("Created file {}", abs.display()))
}

pub fn read_file(arguments: &Value) -> ToolResult {
    let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("");
    let abs = match super::validate_existing_file(path) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("read_file", e),
    };
    let mut raw = match fs::read(&abs) {
        Ok(r) => r,
        Err(e) => return ToolResult::fail("read_file", format!("Could not read file: {}", e)),
    };
    let truncated = raw.len() > MAX_READ_CHARS;
    if truncated {
        raw.truncate(MAX_READ_CHARS);
    }
    let content = String::from_utf8_lossy(&raw).to_string();
    ToolResult {
        success: true,
        message: format!("Read {} ({} chars){}", abs.file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default(), content.chars().count(), if truncated { " - truncated" } else { "" }),
        error: None,
        data: serde_json::json!({ "tool": "read_file", "path": abs.display().to_string(), "content": content, "truncated": truncated }),
    }
}

pub fn list_directory(arguments: &Value) -> ToolResult {
    let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("~");
    let abs = match super::validate_existing_dir(path) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("list_directory", e),
    };
    let mut items: Vec<serde_json::Value> = Vec::new();
    let entries = match fs::read_dir(&abs) {
        Ok(e) => e,
        Err(e) => return ToolResult::fail("list_directory", format!("Could not list directory: {}", e)),
    };
    let mut collected: Vec<(String, PathBuf, bool, u64)> = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        let is_dir = entry.file_type().map(|t| t.is_dir()).unwrap_or(false);
        let size = if is_dir { 0 } else { entry.metadata().map(|m| m.len()).unwrap_or(0) };
        collected.push((entry.file_name().to_string_lossy().to_string(), path.clone(), is_dir, size));
    }
    collected.sort_by(|a, b| a.0.to_lowercase().cmp(&b.0.to_lowercase()));
    for (name, path, is_dir, size) in collected.into_iter().take(MAX_LIST_ITEMS) {
        items.push(serde_json::json!({
            "name": name,
            "path": path.display().to_string(),
            "type": if is_dir { "directory" } else { "file" },
            "size": size,
        }));
    }
    ToolResult {
        success: true,
        message: format!("Listed {} item(s) in {}", items.len(), abs.display()),
        error: None,
        data: serde_json::json!({ "tool": "list_directory", "path": abs.display().to_string(), "items": items }),
    }
}

pub fn delete_file(arguments: &Value) -> ToolResult {
    let path = arguments.get("path").and_then(|v| v.as_str()).unwrap_or("");
    let abs = match validate_path(path) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("delete_file", e),
    };
    if !abs.exists() {
        return ToolResult::fail("delete_file", format!("Path not found: {}", abs.display()));
    }
    let home = dirs::home_dir().map(|h| h.canonicalize().unwrap_or(h)).unwrap_or_default();
    if abs == home {
        return ToolResult::fail("delete_file", "Refusing to delete your home directory.");
    }
    let result = if abs.is_dir() {
        fs::remove_dir_all(&abs)
    } else {
        fs::remove_file(&abs)
    };
    match result {
        Ok(()) => ToolResult::ok("delete_file", format!("Deleted {}", abs.display())),
        Err(e) => ToolResult::fail("delete_file", format!("Delete failed: {}", e)),
    }
}

pub fn move_file(arguments: &Value) -> ToolResult {
    let source = arguments.get("source").and_then(|v| v.as_str()).unwrap_or("");
    let destination = arguments.get("destination").and_then(|v| v.as_str()).unwrap_or("");
    let src = match validate_path(source) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("move_file", e),
    };
    let dst = match validate_path(destination) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("move_file", e),
    };
    if !src.exists() {
        return ToolResult::fail("move_file", format!("Source not found: {}", src.display()));
    }
    if let Some(parent) = dst.parent() {
        let _ = fs::create_dir_all(parent);
    }
    match fs::rename(&src, &dst) {
        Ok(()) => ToolResult::ok("move_file", format!("Moved {} to {}", src.display(), dst.display())),
        Err(e) => ToolResult::fail("move_file", format!("Move failed: {}", e)),
    }
}

fn copy_recursive(src: &Path, dst: &Path) -> std::io::Result<()> {
    if src.is_dir() {
        fs::create_dir_all(dst)?;
        for entry in fs::read_dir(src)? {
            let entry = entry?;
            let target = dst.join(entry.file_name());
            copy_recursive(&entry.path(), &target)?;
        }
    } else {
        if let Some(parent) = dst.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::copy(src, dst)?;
    }
    Ok(())
}

pub fn copy_file(arguments: &Value) -> ToolResult {
    let source = arguments.get("source").and_then(|v| v.as_str()).unwrap_or("");
    let destination = arguments.get("destination").and_then(|v| v.as_str()).unwrap_or("");
    let src = match validate_path(source) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("copy_file", e),
    };
    let dst = match validate_path(destination) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("copy_file", e),
    };
    if !src.exists() {
        return ToolResult::fail("copy_file", format!("Source not found: {}", src.display()));
    }
    match copy_recursive(&src, &dst) {
        Ok(()) => ToolResult::ok("copy_file", format!("Copied {} to {}", src.display(), dst.display())),
        Err(e) => ToolResult::fail("copy_file", format!("Copy failed: {}", e)),
    }
}
