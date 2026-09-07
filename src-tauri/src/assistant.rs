//! PLUTO assistant orchestrator.
//!
//! Receives a natural-language command, plans tool calls with the on-device
//! NLU, executes them through real Rust tools, streams the same event shapes
//! the old backend used (`agent_state`, `execution_step`, `activity`,
//! `action_preview`, `speak`, `error`) and applies the confirmation gate for
//! destructive/terminal actions.

use crate::nlu::{recommend, PlanItem, SessionContext};
use crate::state::{AppState, PendingConfirmation};
use crate::tools::{self, ToolResult};
use serde_json::{json, Value};
use std::sync::atomic::Ordering;
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager};
use tokio::sync::oneshot;

const CONFIRMATION_TIMEOUT_MS: u64 = 180_000;

fn emit(app: &AppHandle, payload: Value) {
    let _ = app.emit("pluto-event", payload);
}

fn set_context_from_args(context: &mut SessionContext, name: &str, args: &Value) {
    match name {
        "open_url" | "browser_search" => {
            if let Some(url) = args.get("url").and_then(|v| v.as_str()) {
                context.current_url = Some(url.to_string());
            }
        }
        "browser_click" => {
            if let Some(index) = args.get("index").and_then(|v| v.as_u64()) {
                context.selected_result_index = Some(index as u32);
            }
        }
        "open_application" | "switch_to_application" => {
            if let Some(app) = args.get("application").and_then(|v| v.as_str()) {
                context.current_app = Some(app.to_string());
            }
        }
        "open_file" | "read_file" | "create_file" | "create_folder" | "list_directory" | "open_folder" | "find_files" => {
            let path = args.get("path").or_else(|| args.get("location")).and_then(|v| v.as_str());
            if let Some(path) = path {
                let expanded = crate::nlu::expand_home(path);
                if !context.recent_files.contains(&expanded) {
                    context.recent_files.insert(0, expanded.clone());
                    context.recent_files.truncate(10);
                }
                if let Some(parent) = std::path::Path::new(&expanded).parent() {
                    context.current_directory = Some(parent.display().to_string());
                }
            }
        }
        _ => {}
    }
}

fn step_id(i: usize) -> String {
    format!("s{}", i)
}

fn step_label(name: &str, args: &Value) -> String {
    let app_str = |k: &str| args.get(k).and_then(|v| v.as_str()).unwrap_or("");
    match name {
        "open_application" => format!("Open {}", app_str("application")),
        "close_application" => format!("Close {}", app_str("application")),
        "switch_to_application" => format!("Switch to {}", app_str("application")),
        "open_url" => format!("Open {}", app_str("url")),
        "browser_search" => format!("Search '{}'", app_str("query")),
        "take_screenshot" => "Take screenshot".to_string(),
        "set_volume" => format!("Set volume to {}", app_str("level")),
        "create_file" => format!("Create file {}", app_str("path")),
        "create_folder" => format!("Create folder {}", app_str("path")),
        "delete_file" => format!("Delete {}", app_str("path")),
        "read_file" => format!("Read {}", app_str("path")),
        "list_directory" => format!("List {}", app_str("path")),
        "get_clipboard" => "Read clipboard".to_string(),
        "copy_to_clipboard" => "Copy to clipboard".to_string(),
        "get_processes" => "List processes".to_string(),
        "kill_process" => format!("Stop {}", app_str("process")),
        "execute_command" => format!("Run '{}'", app_str("command")),
        "send_message" => format!("Message {} on {}", app_str("recipient"), app_str("app")),
        other => other.replace('_', " "),
    }
}

fn preview_type(tool: &str) -> &'static str {
    match tool {
        "delete_file" => "file_delete",
        "move_file" => "file_delete",
        "send_message" => "message",
        "execute_command" | "kill_process" => "command",
        _ => "command",
    }
}

fn preview_payload(tool: &str, args: &Value) -> Value {
    let app_str = |k: &str| args.get(k).and_then(|v| v.as_str()).unwrap_or("").to_string();
    let title = match tool {
        "delete_file" => format!("Delete {}", app_str("path")),
        "move_file" => format!("Move {} to {}", app_str("source"), app_str("destination")),
        "execute_command" => format!("Run command: {}", app_str("command")),
        "kill_process" => format!("Stop process: {}", app_str("process")),
        "send_message" => format!("Send message to {} on {}", app_str("recipient"), app_str("app")),
        _ => format!("Execute: {}", tool),
    };
    let content = args
        .get("content")
        .and_then(|v| v.as_str())
        .or_else(|| args.get("message").and_then(|v| v.as_str()))
        .unwrap_or("")
        .to_string();
    json!({
        "type": preview_type(tool),
        "title": title,
        "path": app_str("path"),
        "content": content,
        "requiresConfirmation": true,
    })
}

fn requires_confirmation(tool: &str, args: &Value) -> bool {
    match tool {
        "delete_file" | "move_file" | "kill_process" | "send_message" => true,
        "execute_command" => {
            crate::tools::terminal::classify_command(args.get("command").and_then(|v| v.as_str()).unwrap_or(""))
                == crate::tools::terminal::CommandSafety::ConfirmRequired
        }
        _ => false,
    }
}

async fn await_confirmation(app: &AppHandle, state: &AppState, tool: &str, args: &Value) -> bool {
    let (tx, mut rx) = oneshot::channel::<bool>();
    let mut pending = state.pending.lock().await;
    *pending = Some(PendingConfirmation { tool: tool.to_string(), arguments: args.clone(), tx });
    drop(pending);

    emit(app, json!({ "type": "action_preview", "preview": preview_payload(tool, args) }));

    let approved = match tokio::time::timeout(
        std::time::Duration::from_millis(CONFIRMATION_TIMEOUT_MS),
        &mut rx,
    )
    .await
    {
        Ok(Ok(value)) => value && !state.cancel.load(Ordering::SeqCst),
        Ok(Err(_)) => false,
        Err(_) => false,
    };

    let mut pending = state.pending.lock().await;
    if let Some(p) = pending.take() {
        let _ = p.tx.send(false);
    }
    approved
}

fn activity_payload(tool: &str, result: &ToolResult) -> Value {
    let category = match tool {
        "open_application" | "close_application" | "switch_to_application" | "list_running_applications" => "app",
        "open_url" | "browser_search" | "browser_click" | "browser_key" | "browser_snapshot" | "close_browser" => "browser",
        "create_file" | "create_folder" | "delete_file" | "read_file" | "list_directory" | "move_file" | "copy_file" | "open_file" | "open_folder" | "find_files" => "file",
        "send_message" | "open_chat_app" => "message",
        _ => "system",
    };
    json!({
        "type": "activity",
        "activity": {
            "id": format!("act-{}-{}", std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_millis(), tool),
            "title": tool.replace('_', " "),
            "description": result.message.chars().take(120).collect::<String>(),
            "timestamp": "Just now",
            "status": if result.success { "success" } else { "error" },
            "category": category,
        }
    })
}

async fn speak_text(app: &AppHandle, text: &str) {
    // Voice is optional: local espeak-ng when present, browser TTS otherwise.
    let tts = tools::voice::tts_synthesize(text);
    let audio = tts.data.get("audio_base64").and_then(|v| v.as_str()).map(|s| s.to_string());
    let engine = tts.data.get("engine").and_then(|v| v.as_str()).unwrap_or("browser").to_string();
    emit(
        app,
        json!({ "type": "speak", "text": text, "audio": audio, "tts": engine }),
    );
}

pub async fn run(app: AppHandle, command: String) {
    // AppState is managed as Arc<AppState> so it can be shared across awaits.
    let state = app.state::<Arc<AppState>>().inner().clone();
    let cancel = state.cancel.clone();
    let was_busy = state.busy.swap(true, Ordering::SeqCst);
    if was_busy {
        emit(
            &app,
            json!({ "type": "error", "error": "PLUTO is still busy with the previous command. Please wait." }),
        );
        emit(&app, json!({ "type": "agent_state", "state": "error", "task": "Busy" }));
        return;
    }
    cancel.store(false, Ordering::SeqCst);

    emit(&app, json!({
        "type": "agent_state", "state": "understanding", "task": "Understanding your request...",
        "data": { "intent": "nlu", "confidence": 0.95, "recommended_tools": [] }
    }));
    tokio::time::sleep(std::time::Duration::from_millis(250)).await;
    emit(&app, json!({
        "type": "agent_state", "state": "thinking", "task": "Reasoning about your request...", "data": {}
    }));
    tokio::time::sleep(std::time::Duration::from_millis(200)).await;

    // Snapshot the session context.
    let ctx = state.context.lock().await.clone();

    let planned = crate::nlu::plan(&command, &ctx);
    let steps: Vec<(&String, &Value)> = planned
        .iter()
        .filter_map(|item| match item {
            PlanItem::Step(step) => Some((&step.name, &step.arguments)),
            _ => None,
        })
        .collect();
    let hints: Vec<String> = planned
        .iter()
        .filter_map(|item| match item {
            PlanItem::Text(t) => Some(t.clone()),
            _ => None,
        })
        .collect();

    if steps.is_empty() {
        let text = hints.last().cloned().unwrap_or_else(crate::nlu::capabilities_reply_public);
        speak_text(&app, &text).await;
        emit(&app, json!({ "type": "agent_state", "state": "success", "task": text, "data": { "response": text } }));
        emit(&app, json!({ "type": "agent_state", "state": "listening", "task": "Ready for your next command." }));
        state.busy.store(false, Ordering::SeqCst);
        return;
    }

    let intent = steps[0].0.clone();
    let confidence = 0.95;
    let recommended_tools = recommend(&command, &ctx);
    emit(&app, json!({
        "type": "agent_state", "state": "planning",
        "task": format!("Planning {} step(s)...", steps.len()),
        "data": { "intent": intent, "confidence": confidence, "recommended_tools": recommended_tools }
    }));
    tokio::time::sleep(std::time::Duration::from_millis(150)).await;

    let mut last_hint = hints.last().cloned();
    for (i, (tool_name, arguments)) in steps.iter().enumerate() {
        if cancel.load(Ordering::SeqCst) {
            break;
        }
        let id = step_id(i);
        let label = step_label(tool_name, arguments);
        emit(&app, json!({ "type": "execution_step", "step": { "id": id, "label": label, "status": "current" } }));

        if requires_confirmation(tool_name, arguments) {
            let approved = await_confirmation(&app, &state, tool_name, arguments).await;
            if !approved {
                let text = format!("Action cancelled. Ready for your next command.");
                emit(&app, json!({ "type": "agent_state", "state": "idle", "task": text, "data": { "response": text } }));
                emit(&app, json!({ "type": "agent_state", "state": "listening", "task": "Ready for your next command." }));
                state.busy.store(false, Ordering::SeqCst);
                return;
            }
        }

        if cancel.load(Ordering::SeqCst) {
            break;
        }
        let result = tools::run_tool(tool_name, arguments).await;

        // Update conversational context.
        {
            let mut context = state.context.lock().await;
            set_context_from_args(&mut context, tool_name, arguments);
        }

        emit(
            &app,
            json!({
                "type": "execution_step",
                "step": { "id": id, "label": label, "status": if result.success { "completed" } else { "error" }, "detail": result.message.chars().take(160).collect::<String>() }
            }),
        );
        emit(&app, activity_payload(tool_name, &result));

        if !result.success {
            let error_text = result.error.unwrap_or_else(|| "An operation failed.".to_string());
            let message = format!("I couldn't complete that, BOSS: {}. I'm still listening - want me to try again?", error_text);
            emit(&app, json!({ "type": "agent_state", "state": "error", "error": message.clone(), "task": message, "data": { "response": message } }));
            speak_text(&app, &message).await;
            emit(&app, json!({ "type": "agent_state", "state": "listening", "task": "Ready for your next command." }));
            state.busy.store(false, Ordering::SeqCst);
            return;
        }
        last_hint = Some(result.message);
    }

    if cancel.load(Ordering::SeqCst) {
        let text = "Stopped, BOSS. Say the word when you need me again.".to_string();
        emit(&app, json!({ "type": "agent_state", "state": "idle", "task": text, "data": { "response": text } }));
        speak_text(&app, &text).await;
        emit(&app, json!({ "type": "agent_state", "state": "listening", "task": "Ready for your next command." }));
        state.busy.store(false, Ordering::SeqCst);
        return;
    }

    let success_text = last_hint.unwrap_or_else(|| "Done, BOSS.".to_string());
    emit(&app, json!({ "type": "agent_state", "state": "success", "task": success_text.clone(), "data": { "response": success_text } }));
    speak_text(&app, &success_text).await;
    emit(&app, json!({ "type": "agent_state", "state": "listening", "task": "Ready for your next command." }));
    state.busy.store(false, Ordering::SeqCst);
}

pub fn cancel(state: &AppState) {
    state.cancel.store(true, Ordering::SeqCst);
}

pub fn reset(state: &AppState) {
    state.cancel.store(true, Ordering::SeqCst);
}
