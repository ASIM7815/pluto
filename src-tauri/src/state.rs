use serde_json::Value;
use std::sync::atomic::AtomicBool;
use std::sync::Arc;
use tokio::sync::{oneshot, Mutex};

use crate::nlu::SessionContext;

pub struct PendingConfirmation {
    pub tool: String,
    pub arguments: Value,
    pub tx: oneshot::Sender<bool>,
}

#[derive(Default)]
pub struct AppState {
    /// True while the assistant is running a command.
    pub busy: AtomicBool,
    /// Cooperative cancellation for the running task.
    pub cancel: Arc<AtomicBool>,
    /// Cancellation flag for an in-progress native microphone capture.
    pub mic_cancel: Arc<AtomicBool>,
    /// Confirmation gate for CONFIRM_REQUIRED tools.
    pub pending: Mutex<Option<PendingConfirmation>>,
    /// Session-scoped conversational context (recent files, cwd, URL...).
    pub context: Mutex<SessionContext>,
}


