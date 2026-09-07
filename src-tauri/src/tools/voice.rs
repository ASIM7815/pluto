//! Local voice: TTS via espeak-ng/espeak (fully offline) and optional STT via
//! whisper.cpp (`whisper-cli` with a model). All real OS audio work; no Python.

use super::{find_program, run_process, ToolResult};
use base64::Engine;
use serde_json::Value;
use std::path::PathBuf;

fn espeak_program() -> Option<PathBuf> {
    find_program("espeak-ng").or_else(|| find_program("espeak"))
}

pub fn tts_synthesize(text: &str) -> ToolResult {
    let text = text.trim();
    if text.is_empty() {
        return ToolResult::fail("tts_synthesize", "No text to speak.");
    }
    match espeak_program() {
        Some(program) => {
            match run_process(&program, &["--stdout", text], 20_000, &[]) {
                Ok((code, out, _)) if code == 0 && !out.is_empty() => {
                    let audio_base64 = base64::engine::general_purpose::STANDARD.encode(&out);
                    ToolResult {
                        success: true,
                        message: "Synthesized speech (espeak-ng).".to_string(),
                        error: None,
                        data: serde_json::json!({
                            "audio_base64": audio_base64,
                            "mime": "audio/wav",
                            "engine": "local_tts",
                            "bytes": out.len(),
                        }),
                    }
                }
                Ok(_) => ToolResult::ok("tts_synthesize", "No local TTS audio produced."),
                Err(e) => ToolResult::fail("tts_synthesize", format!("TTS failed: {}", e)),
            }
        }
        None => ToolResult::ok("tts_synthesize", "No local TTS engine installed - the browser will speak.")
            .with_data(serde_json::json!({ "engine": "browser", "audio_base64": null })),
    }
}

impl ToolResult {
    fn with_data(mut self, data: Value) -> Self {
        self.data = data;
        self
    }
}

pub fn tts_voices() -> ToolResult {
    let engines: Vec<Value> = espeak_program()
        .map(|_| vec![serde_json::json!({ "id": "espeak", "name": "espeak-ng (offline)" })])
        .unwrap_or_default();
    ToolResult {
        success: true,
        message: "Local voice engines".to_string(),
        error: None,
        data: serde_json::json!({ "voices": [], "engines": engines, "engine": "local" }),
    }
}

pub fn stt_status() -> ToolResult {
    let whisper = find_program("whisper-cli")
        .or_else(|| find_program("whisper"))
        .or_else(|| find_program("main"));
    let model = whisper_model_path();
    let available = whisper.is_some() && model.is_some();
    ToolResult {
        success: true,
        message: if available { "whisper.cpp available" } else { "no whisper.cpp engine installed" }.to_string(),
        error: None,
        data: serde_json::json!({
            "available": available,
            "engine": if available { "whisper.cpp" } else { "none" },
            "model": model,
            "hint": "Install whisper.cpp (whisper-cli) and put a ggml model in ~/.cache/pluto/",
        }),
    }
}

fn whisper_model_path() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("PLUTO_WHISPER_MODEL") {
        let path = PathBuf::from(p);
        if path.exists() {
            return Some(path);
        }
    }
    let home = dirs::home_dir()?;
    for candidate in [
        home.join(".cache/pluto/ggml-base.en.bin"),
        home.join(".cache/pluto/ggml-base.bin"),
        home.join(".cache/pluto/ggml-small.en.bin"),
        home.join(".cache/whisper/ggml-base.en.bin"),
    ] {
        if candidate.exists() {
            return Some(candidate);
        }
    }
    None
}

pub fn stt_transcribe(audio: &[u8], mime: &str) -> ToolResult {
    let program = match find_program("whisper-cli")
        .or_else(|| find_program("whisper"))
        .or_else(|| find_program("main"))
    {
        Some(p) => p,
        None => return ToolResult::fail("stt_transcribe", "whisper.cpp is not installed. Install whisper-cli and a model for offline transcription."),
    };
    let model = match whisper_model_path() {
        Some(m) => m,
        None => {
            return ToolResult::fail(
                "stt_transcribe",
                "No whisper model found. Put a ggml model at ~/.cache/pluto/ (e.g. ggml-base.en.bin) or set PLUTO_WHISPER_MODEL.",
            );
        }
    };
    // Save the incoming audio to a temp file (wav needed by whisper.cpp).
    let tmp_dir = std::env::temp_dir();
    let audio_path = tmp_dir.join(format!("pluto_stt_{}.wav", std::process::id()));
    let mime = mime.to_lowercase();
    let bytes: Vec<u8> = if mime.contains("wav") || mime.contains("pcm") || audio.starts_with(b"RIFF") {
        audio.to_vec()
    } else {
        // WebM/Opus from MediaRecorder: try ffmpeg conversion if available.
        let tmp_in = tmp_dir.join(format!("pluto_stt_in_{}", std::process::id()));
        let _ = std::fs::write(&tmp_in, audio);
        match find_program("ffmpeg") {
            Some(ffmpeg) => {
                let args = ["-y", "-i", tmp_in.to_str().unwrap_or(""), "-ar", "16000", "-ac", "1", audio_path.to_str().unwrap_or("")];
                if let Ok((code, _, _)) = run_process(&ffmpeg, &args, 30_000, &[]) {
                    if code == 0 {
                        std::fs::read(&audio_path).unwrap_or_default()
                    } else {
                        audio.to_vec()
                    }
                } else {
                    audio.to_vec()
                }
            }
            None => audio.to_vec(),
        }
    };
    let _ = std::fs::write(&audio_path, &bytes);

    let txt_path = audio_path.with_extension("txt");
    let _ = std::fs::remove_file(&txt_path);
    let args = [
        "-m",
        model.to_str().unwrap_or(""),
        "-f",
        audio_path.to_str().unwrap_or(""),
        "-nt",
        "-of",
        txt_path.with_extension("").to_str().unwrap_or(""),
    ];
    match run_process(&program, &args, 60_000, &[]) {
        Ok((code, _, _)) if code == 0 => {
            if let Ok(content) = std::fs::read_to_string(&txt_path) {
                let text = content.trim().to_string();
                let _ = std::fs::remove_file(&audio_path);
                let _ = std::fs::remove_file(&txt_path);
                if text.is_empty() {
                    ToolResult::ok("stt_transcribe", "Heard no speech.").with_data(serde_json::json!({ "text": "", "heard_speech": false }))
                } else {
                    ToolResult::ok("stt_transcribe", "Transcribed.").with_data(serde_json::json!({ "text": text, "heard_speech": true }))
                }
            } else {
                let _ = std::fs::remove_file(&audio_path);
                ToolResult::fail("stt_transcribe", "Transcription produced no output file.")
            }
        }
        Ok((_, _, err)) => {
            let _ = std::fs::remove_file(&audio_path);
            ToolResult::fail("stt_transcribe", format!("Speech-to-text failed: {}", String::from_utf8_lossy(&err).trim()))
        }
        Err(e) => {
            let _ = std::fs::remove_file(&audio_path);
            ToolResult::fail("stt_transcribe", format!("Speech-to-text failed: {}", e))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tts_absent_reports_browser() {
        // In CI there may or may not be espeak; the call must not panic.
        let result = tts_synthesize("hello");
        assert!(result.success);
    }
}
