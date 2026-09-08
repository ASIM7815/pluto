//! Tauri command surface. Everything here is invoked from the webview via
//! `@tauri-apps/api` - no HTTP, no ports, no external runtime.

use crate::state::AppState;
use crate::tools;
use serde::Serialize;
use serde_json::{json, Value};
use std::sync::Arc;
use tauri::{AppHandle, Manager};

async fn run_sync(f: fn(&Value) -> tools::ToolResult, args: Value) -> tools::ToolResult {
    tauri::async_runtime::spawn_blocking(move || f(&args))
        .await
        .unwrap_or_else(|_| tools::ToolResult::fail("system", "Background task panicked"))
}

fn public_result(result: tools::ToolResult) -> Result<Value, String> {
    Ok(json!({
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
    }))
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemMetricsPayload {
    pub cpu: u32,
    pub ram: u32,
    pub storage: u32,
    pub gpu: u32,
    pub temp: u32,
    pub network_up: String,
    pub network_down: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemStatsPayload {
    pub cpu: u32,
    pub ram: u32,
    pub storage: u32,
    pub uptime: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemInfoPayload {
    pub os: String,
    pub distro: String,
    pub host: String,
    pub uptime: String,
    pub security_status: String,
    pub voice_engine: String,
    pub llm_engine: String,
}

fn format_uptime(total_seconds: u64) -> String {
    let days = total_seconds / 86_400;
    let hours = (total_seconds % 86_400) / 3_600;
    let minutes = (total_seconds % 3_600) / 60;
    if days > 0 {
        format!("{}d {}h {}m", days, hours, minutes)
    } else {
        format!("{}h {}m", hours, minutes)
    }
}

fn system_data() -> (u32, u32, u32) {
    let mut sys = sysinfo::System::new_all();
    sys.refresh_all();
    let cpu = sys.global_cpu_usage().round().clamp(0.0, 100.0) as u32;
    let ram = if sys.total_memory() == 0 {
        0
    } else {
        ((sys.used_memory() as f64 / sys.total_memory() as f64) * 100.0).round() as u32
    };
    let disks = sysinfo::Disks::new_with_refreshed_list();
    let total: u64 = disks.iter().map(|d| d.total_space()).sum();
    let free: u64 = disks.iter().map(|d| d.available_space()).sum();
    let storage = if total == 0 { 0 } else { (((total - free) as f64 / total as f64) * 100.0).round() as u32 };
    (cpu, ram, storage)
}

// ---------------------------------------------------------------------------
// Assistant session
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn pluto_execute_command(app: AppHandle, command: String) -> Result<(), String> {
    let state = app.state::<Arc<AppState>>().inner().clone();
    crate::assistant::run(app, command).await;
    let _ = state;
    Ok(())
}

#[tauri::command]
pub fn pluto_interrupt(app: AppHandle) {
    let state = app.state::<Arc<AppState>>().inner().clone();
    crate::assistant::cancel(&state);
    let _ = app;
}

#[tauri::command]
pub fn pluto_reset(app: AppHandle) {
    let state = app.state::<Arc<AppState>>().inner().clone();
    crate::assistant::cancel(&state);
    tauri::async_runtime::spawn(async move {
        let mut ctx = state.context.lock().await;
        *ctx = crate::nlu::SessionContext::default();
    });
    let _ = app;
}

#[tauri::command]
pub async fn pluto_confirm(app: AppHandle, _action: String) -> Result<(), String> {
    let state = app.state::<Arc<AppState>>().inner().clone();
    let mut pending = state.pending.lock().await;
    if let Some(p) = pending.take() {
        let _ = p.tx.send(true);
    }
    let _ = app;
    Ok(())
}

#[tauri::command]
pub async fn pluto_reject(app: AppHandle, _action: String) -> Result<(), String> {
    let state = app.state::<Arc<AppState>>().inner().clone();
    let mut pending = state.pending.lock().await;
    if let Some(p) = pending.take() {
        let _ = p.tx.send(false);
    }
    let _ = app;
    Ok(())
}

// ---------------------------------------------------------------------------
// System information
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn pluto_get_system_metrics() -> Result<SystemMetricsPayload, String> {
    let (cpu, ram, storage) = system_data();
    Ok(SystemMetricsPayload {
        cpu,
        ram,
        storage,
        gpu: 0,
        temp: 0,
        network_up: "-".into(),
        network_down: "-".into(),
    })
}

#[tauri::command]
pub async fn pluto_get_system_stats() -> Result<SystemStatsPayload, String> {
    let (cpu, ram, storage) = system_data();
    let uptime = format_uptime(sysinfo::System::uptime());
    Ok(SystemStatsPayload { cpu, ram, storage, uptime })
}

#[tauri::command]
pub async fn pluto_get_system_info() -> Result<SystemInfoPayload, String> {
    let mut sys = sysinfo::System::new_all();
    sys.refresh_all();
    let os = sysinfo::System::long_os_version()
        .or_else(|| sysinfo::System::os_version())
        .unwrap_or_else(|| "Linux".to_string());
    let distro = std::fs::read_to_string("/etc/os-release")
        .ok()
        .and_then(|content| {
            content
                .lines()
                .find(|l| l.starts_with("PRETTY_NAME="))
                .map(|l| l.trim_start_matches("PRETTY_NAME=").trim_matches('"').to_string())
        })
        .unwrap_or_else(|| os.clone());
    Ok(SystemInfoPayload {
        os,
        distro,
        host: sysinfo::System::host_name().unwrap_or_else(|| "PLUTO-DESKTOP".to_string()),
        uptime: format_uptime(sysinfo::System::uptime()),
        security_status: "Sandboxed & Confirmation-gated".to_string(),
        voice_engine: "PLUTO Local TTS (espeak-ng)".to_string(),
        llm_engine: "PLUTO Pattern Intelligence (on-device)".to_string(),
    })
}

// ---------------------------------------------------------------------------
// OS actions (direct wrappers used by the UI bridge and the assistant tools)
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn pluto_take_screenshot(
    area: String,
    directory: Option<String>,
    filename: Option<String>,
) -> Result<Value, String> {
    let args = json!({ "area": area, "directory": directory, "filename": filename });
    let result = run_sync(tools::system::take_screenshot, args).await;
    public_result(result)
}

#[tauri::command]
pub async fn pluto_set_clipboard(text: String) -> Result<Value, String> {
    public_result(run_sync(tools::system::copy_to_clipboard, json!({ "text": text })).await)
}

#[tauri::command]
pub async fn pluto_get_clipboard() -> Result<Value, String> {
    public_result(run_sync(tools::system::get_clipboard, json!({})).await)
}

#[tauri::command]
pub async fn pluto_set_volume(level: u32) -> Result<Value, String> {
    public_result(run_sync(tools::system::set_volume, json!({ "level": level })).await)
}

#[tauri::command]
pub async fn pluto_get_volume() -> Result<Value, String> {
    public_result(run_sync(tools::system::get_volume, json!({})).await)
}

#[tauri::command]
pub async fn pluto_get_processes(limit: Option<u32>) -> Result<Value, String> {
    public_result(run_sync(tools::system::get_processes, json!({ "limit": limit.unwrap_or(10) })).await)
}

#[tauri::command]
pub async fn pluto_kill_process(process: String) -> Result<Value, String> {
    public_result(run_sync(tools::system::kill_process, json!({ "process": process })).await)
}

#[tauri::command]
pub async fn pluto_open_url(url: String) -> Result<Value, String> {
    public_result(run_sync(tools::apps::open_url, json!({ "url": url })).await)
}

#[tauri::command]
pub async fn pluto_launch_application(
    application: String,
    arguments: Vec<String>,
) -> Result<Value, String> {
    public_result(run_sync(tools::apps::open_application, json!({ "application": application, "arguments": arguments })).await)
}

#[tauri::command]
pub async fn pluto_open_file(path: String) -> Result<Value, String> {
    public_result(run_sync(tools::files::open_file, json!({ "path": path })).await)
}

#[tauri::command]
pub async fn pluto_open_folder(path: String) -> Result<Value, String> {
    public_result(run_sync(tools::files::open_folder, json!({ "path": path })).await)
}

#[tauri::command]
pub async fn pluto_create_folder(path: String) -> Result<Value, String> {
    public_result(run_sync(tools::files::create_folder, json!({ "path": path })).await)
}

#[tauri::command]
pub async fn pluto_create_file(path: String, content: Option<String>) -> Result<Value, String> {
    public_result(run_sync(tools::files::create_file, json!({ "path": path, "content": content.unwrap_or_default() })).await)
}

#[tauri::command]
pub async fn pluto_read_file(path: String) -> Result<Value, String> {
    public_result(run_sync(tools::files::read_file, json!({ "path": path })).await)
}

#[tauri::command]
pub async fn pluto_list_directory(path: Option<String>) -> Result<Value, String> {
    public_result(run_sync(tools::files::list_directory, json!({ "path": path.unwrap_or_else(|| "~".to_string()) })).await)
}

#[tauri::command]
pub async fn pluto_delete_file(path: String) -> Result<Value, String> {
    public_result(run_sync(tools::files::delete_file, json!({ "path": path })).await)
}

#[tauri::command]
pub async fn pluto_copy_file(source: String, destination: String) -> Result<Value, String> {
    public_result(run_sync(tools::files::copy_file, json!({ "source": source, "destination": destination })).await)
}

#[tauri::command]
pub async fn pluto_move_file(source: String, destination: String) -> Result<Value, String> {
    public_result(run_sync(tools::files::move_file, json!({ "source": source, "destination": destination })).await)
}

#[tauri::command]
pub async fn pluto_find_files(query: String, location: Option<String>) -> Result<Value, String> {
    public_result(run_sync(tools::files::find_files, json!({ "query": query, "location": location.unwrap_or_else(|| "~".to_string()) })).await)
}

#[tauri::command]
pub async fn pluto_execute_terminal(command: String) -> Result<Value, String> {
    public_result(run_sync(tools::terminal::execute_command, json!({ "command": command })).await)
}

#[tauri::command]
pub async fn pluto_send_message(recipient: String, message: String) -> Result<Value, String> {
    public_result(run_sync(tools::apps::send_message, json!({ "recipient": recipient, "message": message, "app": "whatsapp" })).await)
}

// ---------------------------------------------------------------------------
// Voice (TTS/STT)
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn pluto_tts_synthesize(text: String) -> Result<Value, String> {
    let result = tools::voice::tts_synthesize(&text);
    if !result.success {
        return Err(result.message);
    }
    Ok(result.data.clone())
}

#[tauri::command]
pub async fn pluto_tts_voices() -> Result<Value, String> {
    let result = tools::voice::tts_voices();
    Ok(result.data.clone())
}

#[tauri::command]
pub async fn pluto_stt_status() -> Result<Value, String> {
    let result = tools::voice::stt_status();
    Ok(result.data.clone())
}

#[tauri::command]
pub async fn pluto_stt_transcribe(audio: Vec<u8>, mime: String) -> Result<Value, String> {
    let result = tools::voice::stt_transcribe(&audio, &mime);
    if result.success {
        Ok(result.data.clone())
    } else {
        Err(result.message)
    }
}

#[tauri::command]
pub fn pluto_is_available() -> bool {
    true
}
