//! Functional smoke tests for the PLUTO Rust backend.
//!
//! These run under Xvfb on CI (`PLUTO_SMOKE` is implied by `--ignored`):
//! they exercise the real clipboard, a real X11 screenshot and the full
//! filesystem tool chain - no mocks.

use pluto_lib::tools;
use serde_json::json;
use std::path::Path;

fn tmp_root() -> std::path::PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| std::env::temp_dir())
        .join(format!("pluto_smoke_{}", std::process::id()))
}

#[test]
#[ignore]
fn clipboard_roundtrip() {
    let mut clipboard = arboard::Clipboard::new().expect("clipboard available under Xvfb");
    clipboard.set_text("pluto-smoke-42".to_string()).expect("copy");
    let text = clipboard.get_text().expect("paste");
    assert_eq!(text, "pluto-smoke-42");
    println!("CLIPBOARD_OK: {text}");
}

#[test]
#[ignore]
fn screenshot_x11_capture() {
    let result = tools::system::take_screenshot(&json!({ "area": "full" }));
    assert!(result.success, "screenshot failed: {}", result.message);
    let path = result.data["path"].as_str().expect("screenshot path");
    assert!(Path::new(path).exists(), "screenshot file not found: {}", path);
    let meta = std::fs::metadata(path).expect("metadata");
    assert!(meta.len() > 0, "screenshot is empty");
    println!("SCREENSHOT_OK: {} bytes at {}", meta.len(), path);
    let _ = std::fs::remove_file(path);
}

#[test]
#[ignore]
fn file_tools_roundtrip() {
    let root = tmp_root();
    let folder = root.join("folder");
    let file = folder.join("hello.txt");
    let dest = folder.join("hello-copy.txt");
    let moved = folder.join("hello-moved.txt");

    let created = tools::files::create_folder(&json!({ "path": folder.display().to_string() }));
    assert!(created.success, "create_folder: {}", created.message);

    let written = tools::files::create_file(&json!({ "path": file.display().to_string(), "content": "hello from pluto" }));
    assert!(written.success, "create_file: {}", written.message);

    let read = tools::files::read_file(&json!({ "path": file.display().to_string() }));
    assert!(read.success, "read_file: {}", read.message);
    assert_eq!(read.data["content"], "hello from pluto");

    let list = tools::files::list_directory(&json!({ "path": folder.display().to_string() }));
    assert!(list.success, "list_directory: {}", list.message);
    assert!(!list.data["items"].as_array().unwrap().is_empty(), "expected at least one item");

    let copied = tools::files::copy_file(&json!({
        "source": file.display().to_string(),
        "destination": dest.display().to_string()
    }));
    assert!(copied.success, "copy_file: {}", copied.message);

    let moved_f = tools::files::move_file(&json!({
        "source": dest.display().to_string(),
        "destination": moved.display().to_string()
    }));
    assert!(moved_f.success, "move_file: {}", moved_f.message);

    let found = tools::files::find_files(&json!({
        "query": "hello",
        "location": root.display().to_string()
    }));
    assert!(found.success, "find_files: {}", found.message);

    let deleted = tools::files::delete_file(&json!({ "path": folder.display().to_string() }));
    assert!(deleted.success, "delete_file: {}", deleted.message);
    assert!(!folder.exists(), "folder should be gone");

    println!("FILE_TOOLS_OK: create/read/list/copy/move/find/delete all passed");
}
