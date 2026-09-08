//! PLUTO - Rust/Tauri desktop backend.

pub mod assistant;
pub mod commands;
pub mod nlu;
pub mod state;
pub mod tools;

use std::sync::Arc;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let state = Arc::new(state::AppState::default());

    tauri::Builder::default()
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            commands::pluto_execute_command,
            commands::pluto_interrupt,
            commands::pluto_reset,
            commands::pluto_confirm,
            commands::pluto_reject,
            commands::pluto_get_system_metrics,
            commands::pluto_get_system_stats,
            commands::pluto_get_system_info,
            commands::pluto_take_screenshot,
            commands::pluto_set_clipboard,
            commands::pluto_get_clipboard,
            commands::pluto_set_volume,
            commands::pluto_get_volume,
            commands::pluto_get_processes,
            commands::pluto_kill_process,
            commands::pluto_open_url,
            commands::pluto_launch_application,
            commands::pluto_open_file,
            commands::pluto_open_folder,
            commands::pluto_create_folder,
            commands::pluto_create_file,
            commands::pluto_read_file,
            commands::pluto_list_directory,
            commands::pluto_delete_file,
            commands::pluto_copy_file,
            commands::pluto_move_file,
            commands::pluto_find_files,
            commands::pluto_execute_terminal,
            commands::pluto_send_message,
            commands::pluto_tts_synthesize,
            commands::pluto_tts_voices,
            commands::pluto_stt_status,
            commands::pluto_stt_record,
            commands::pluto_voice_cancel,
            commands::pluto_stt_transcribe,
            commands::pluto_is_available,
        ])
        .run(tauri::generate_context!())
        .expect("error while running PLUTO");
}
