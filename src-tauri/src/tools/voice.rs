//! Local voice.
//!
//! TTS: best free voice on the system, detected at runtime:
//!   1. Piper (neural, system-installed voices - female preferred)
//!   2. pico2wave (libttspico - female-sounding en-US by default)
//!   3. espeak-ng with a female voice variant (+f3) and natural speed
//!   4. espeak (final fallback)
//! If no local engine exists the caller falls back to browser speech and
//! PLUTO keeps working (voice output is never fatal).
//!
//! STT: native microphone capture (cpal) with a lightweight energy VAD,
//! recorded as 16 kHz mono WAV and passed to whisper.cpp (`whisper-cli`) when
//! installed. The model stays external/downloadable (`~/.cache/pluto/`), never
//! inside the .deb. When whisper.cpp is missing PLUTO reports it clearly
//! instead of failing silently.

use super::{find_program, run_process, ToolResult};
use base64::Engine;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::Sender;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

// ---------------------------------------------------------------------------
// TTS - engine chain
// ---------------------------------------------------------------------------

/// Female voice names preferred for Piper (external voices, never bundled).
const PIPER_PREFERRED: &[&str] = &[
    "en_US-amy",
    "en_GB-alba",
    "en_US-lessac",
    "en_GB-kathleen",
    "en_US-kristin",
    "en_US-l2arctic",
    "en_US-libritts_r",
];

/// espeak-ng/espeak voice variants in preference order (female first, then
/// plain clear voices). espeak-ng voice variants: +f1..+f5 female.
const ESPEAK_VARIANTS: &[&str] = &[
    "en-us+f3",
    "en-us+f2",
    "en-gb+f3",
    "en-us",
    "en-gb",
    "en",
    "",
];

struct TtsAudio {
    bytes: Vec<u8>,
    engine: &'static str,
    engine_label: String,
}

fn espeak_binary() -> Option<(&'static str, PathBuf)> {
    find_program("espeak-ng")
        .map(|p| ("espeak-ng", p))
        .or_else(|| find_program("espeak").map(|p| ("espeak", p)))
}

fn voice_score(name: &str) -> usize {
    for (i, preferred) in PIPER_PREFERRED.iter().enumerate() {
        if name.contains(preferred) {
            return i;
        }
    }
    999
}

fn collect_onnx(dir: &Path, out: &mut Vec<(usize, PathBuf)>, depth: usize) {
    if depth > 5 {
        return;
    }
    let Ok(entries) = std::fs::read_dir(dir) else { return };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_onnx(&path, out, depth + 1);
        } else if path.extension().map(|e| e == "onnx").unwrap_or(false) {
            let name = path
                .file_name()
                .map(|f| f.to_string_lossy().to_string())
                .unwrap_or_default();
            out.push((voice_score(&name), path));
        }
    }
}

/// Locate a Piper voice installed on the system (never bundled in the .deb).
fn piper_voice() -> Option<PathBuf> {
    if let Ok(path) = std::env::var("PLUTO_PIPER_VOICE") {
        let pb = PathBuf::from(&path);
        if pb.is_file() {
            return Some(pb);
        }
    }
    let home = dirs::home_dir()?;
    let roots = [
        home.join(".local/share/piper-voices"),
        PathBuf::from("/usr/share/piper-voices"),
        PathBuf::from("/usr/local/share/piper-voices"),
    ];
    let mut found: Vec<(usize, PathBuf)> = Vec::new();
    for root in roots {
        if root.is_dir() {
            collect_onnx(&root, &mut found, 0);
        }
    }
    if found.is_empty() {
        return None;
    }
    found.sort_by(|a, b| {
        a.0.cmp(&b.0).then_with(|| {
            let an = a.1.file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default();
            let bn = b.1.file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default();
            an.cmp(&bn)
        })
    });
    found.first().map(|(_, p)| p.clone())
}

fn tmp_file(kind: &str, ext: &str) -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.subsec_nanos())
        .unwrap_or(0);
    std::env::temp_dir().join(format!("pluto_{}_{}_{}.{}", kind, std::process::id(), nanos, ext))
}

/// Run a process with text fed to stdin; returns (code, stdout, stderr).
fn run_process_stdin(
    program: &Path,
    args: &[&str],
    timeout_ms: u64,
    stdin_data: &[u8],
) -> Result<(i32, Vec<u8>, Vec<u8>), String> {
    use std::io::{Read, Write};
    use std::process::Stdio;

    let mut cmd = std::process::Command::new(program);
    cmd.args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = cmd.spawn().map_err(|e| format!("Failed to run {}: {}", program.display(), e))?;
    if let Some(mut stdin) = child.stdin.take() {
        let _ = stdin.write_all(stdin_data);
    }
    let mut stdout = child.stdout.take().map(|mut s| {
        std::thread::spawn(move || {
            let mut buf = Vec::new();
            let _ = s.read_to_end(&mut buf);
            buf
        })
    });
    let stderr = child.stderr.take().map(|mut s| {
        std::thread::spawn(move || {
            let mut buf = Vec::new();
            let _ = s.read_to_end(&mut buf);
            buf
        })
    });

    let start = Instant::now();
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
                    break;
                }
                std::thread::sleep(Duration::from_millis(30));
            }
        }
    }
    let out = stdout.take().and_then(|h| h.join().ok()).unwrap_or_default();
    let err = stderr.and_then(|h| h.join().ok()).unwrap_or_default();
    let code = status.map(|s| s.code().unwrap_or(-1)).unwrap_or(-1);
    Ok((code, out, err))
}

fn try_piper(text: &str) -> Option<TtsAudio> {
    let program = find_program("piper")?;
    let model = piper_voice()?;
    let wav_path = tmp_file("tts", "wav");
    let args = ["-m", model.to_str()?, "-f", wav_path.to_str()?];
    let status = run_process_stdin(&program, &args, 120_000, text.as_bytes());
    let (code, _, _) = match status {
        Ok(v) => v,
        Err(_) => {
            let _ = std::fs::remove_file(&wav_path);
            return None;
        }
    };
    if code != 0 {
        let _ = std::fs::remove_file(&wav_path);
        return None;
    }
    let bytes = std::fs::read(&wav_path).unwrap_or_default();
    let _ = std::fs::remove_file(&wav_path);
    if bytes.len() <= 44 {
        return None;
    }
    let name = model
        .file_name()
        .map(|f| f.to_string_lossy().to_string())
        .unwrap_or_else(|| "piper".to_string());
    Some(TtsAudio {
        bytes,
        engine: "piper",
        engine_label: format!("Piper ({})", name.trim_end_matches(".onnx")),
    })
}

fn try_pico2wave(text: &str) -> Option<TtsAudio> {
    let program = find_program("pico2wave")?;
    let wav_path = tmp_file("tts", "wav");
    let args = ["-w", wav_path.to_str()?, text];
    let bytes = match run_process(&program, &args, 30_000, &[]) {
        Ok((code, _, _)) if code == 0 => std::fs::read(&wav_path).ok().filter(|b| b.len() > 44),
        _ => None,
    };
    let _ = std::fs::remove_file(&wav_path);
    bytes.map(|bytes| TtsAudio {
        bytes,
        engine: "pico2wave",
        engine_label: "pico2wave (en-US)".to_string(),
    })
}

fn try_espeak(text: &str) -> Option<TtsAudio> {
    let (binary_name, program) = espeak_binary()?;
    for variant in ESPEAK_VARIANTS {
        let mut args: Vec<&str> = vec!["--stdout", "-s", "160", "-p", "50"];
        if !variant.is_empty() {
            args.push("-v");
            args.push(variant);
        }
        args.push(text);
        if let Ok((code, out, _)) = run_process(&program, &args, 30_000, &[]) {
            if code == 0 && out.len() > 44 {
                let label = if variant.is_empty() {
                    binary_name.to_string()
                } else {
                    format!("{} ({})", binary_name, variant)
                };
                return Some(TtsAudio {
                    bytes: out,
                    engine: binary_name,
                    engine_label: label,
                });
            }
        }
    }
    None
}

fn tts_audio(text: &str) -> (Option<TtsAudio>, &'static str) {
    let text = text.trim();
    if let Some(audio) = try_piper(text) {
        return (Some(audio), "piper");
    }
    if let Some(audio) = try_pico2wave(text) {
        return (Some(audio), "pico2wave");
    }
    if let Some(audio) = try_espeak(text) {
        return (Some(audio), "espeak");
    }
    (None, "none")
}

pub fn tts_synthesize(text: &str) -> ToolResult {
    let text = text.trim();
    if text.is_empty() {
        return ToolResult::fail("tts_synthesize", "No text to speak.");
    }
    match tts_audio(text) {
        (Some(audio), _) => {
            let audio_base64 = base64::engine::general_purpose::STANDARD.encode(&audio.bytes);
            ToolResult {
                success: true,
                message: format!("Synthesized speech ({}).", audio.engine_label),
                error: None,
                data: json!({
                    "audio_base64": audio_base64,
                    "mime": "audio/wav",
                    "engine": audio.engine,
                    "engine_label": audio.engine_label,
                    "bytes": audio.bytes.len(),
                }),
            }
        }
        (None, _) => ToolResult::ok("tts_synthesize", "No local TTS engine installed - falling back to browser speech.")
            .with_data(json!({ "engine": "browser", "audio_base64": Value::Null, "mime": "audio/wav", "bytes": 0 })),
    }
}

impl ToolResult {
    fn with_data(mut self, data: serde_json::Value) -> Self {
        self.data = data;
        self
    }
}

/// Human-readable label of the TTS engine PLUTO would use right now.
pub fn voice_engine_label() -> String {
    if let Some(path) = piper_voice() {
        let name = path
            .file_name()
            .map(|f| f.to_string_lossy().to_string())
            .unwrap_or_else(|| "piper".to_string());
        return format!("PLUTO Voice (Piper: {})", name.trim_end_matches(".onnx"));
    }
    if find_program("pico2wave").is_some() {
        return "PLUTO Voice (pico2wave en-US)".to_string();
    }
    if espeak_binary().is_some() {
        return "PLUTO Voice (espeak-ng, female voice)".to_string();
    }
    "PLUTO Voice (browser fallback)".to_string()
}

pub fn tts_voices() -> ToolResult {
    let mut engines: Vec<Value> = Vec::new();
    let mut primary = "none";
    if let Some(path) = piper_voice() {
        let name = path
            .file_name()
            .map(|f| f.to_string_lossy().to_string())
            .unwrap_or_else(|| "piper".to_string());
        engines.push(json!({ "id": "piper", "name": format!("Piper ({})", name.trim_end_matches(".onnx")) }));
        if primary == "none" {
            primary = "piper";
        }
    }
    if find_program("pico2wave").is_some() {
        engines.push(json!({ "id": "pico2wave", "name": "pico2wave (en-US)" }));
        if primary == "none" {
            primary = "pico2wave";
        }
    }
    if espeak_binary().is_some() {
        engines.push(json!({ "id": "espeak-ng", "name": "espeak-ng (+f3 female voice)" }));
        if primary == "none" {
            primary = "espeak-ng";
        }
    }
    ToolResult {
        success: true,
        message: "Local voice engines".to_string(),
        error: None,
        data: json!({ "voices": [], "engines": engines, "engine": primary, "preference": "piper -> pico2wave -> espeak-ng(female) -> espeak" }),
    }
}

// ---------------------------------------------------------------------------
// STT - native microphone capture (cpal) + optional whisper.cpp
// ---------------------------------------------------------------------------

fn whisper_program() -> Option<PathBuf> {
    find_program("whisper-cli")
        .or_else(|| find_program("whisper"))
        .or_else(|| find_program("main"))
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

fn whisper_hint() -> String {
    "Install the whisper.cpp CLI and put a small ggml model in ~/.cache/pluto/ \
     (e.g. ggml-base.en.bin, ~75 MB, from https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin) \
     or set PLUTO_WHISPER_MODEL to its path."
        .to_string()
}

pub fn stt_status() -> ToolResult {
    let whisper = whisper_program();
    let model = whisper_model_path();
    let available = whisper.is_some() && model.is_some();
    let engine = if available {
        "whisper.cpp"
    } else if whisper.is_some() {
        "whisper.cpp (no model)"
    } else {
        "none"
    };
    ToolResult {
        success: true,
        message: if available {
            "whisper.cpp available - voice input ready"
        } else if whisper.is_some() {
            "whisper.cpp installed but no model found"
        } else {
            "no speech-to-text engine installed"
        }
        .to_string(),
        error: None,
        data: json!({
            "available": available,
            "engine": engine,
            "model": model,
            "voice_input": "native (cpal)",
            "hint": whisper_hint(),
        }),
    }
}

/// Write a canonical 16-bit PCM WAV (mono) for the given samples at `rate`.
fn wav_bytes(samples: &[i16], rate: u32) -> Vec<u8> {
    let data_len = samples.len() * 2;
    let mut out = Vec::with_capacity(44 + data_len);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len as u32).to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes()); // PCM
    out.extend_from_slice(&1u16.to_le_bytes()); // mono
    out.extend_from_slice(&rate.to_le_bytes());
    out.extend_from_slice(&(rate * 2).to_le_bytes()); // byte rate
    out.extend_from_slice(&2u16.to_le_bytes()); // block align
    out.extend_from_slice(&16u16.to_le_bytes()); // bits
    out.extend_from_slice(b"data");
    out.extend_from_slice(&(data_len as u32).to_le_bytes());
    for s in samples {
        out.extend_from_slice(&s.to_le_bytes());
    }
    out
}

struct CapturePcm {
    samples: Vec<i16>,
    spoke: bool,
    cancelled: bool,
}

/// Nearest-neighbour resampler to 16 kHz mono with channel averaging.
struct Downmixer {
    channels: u16,
    /// Output rate relative to the input rate as a float step.
    step: f64,
    acc: f64,
}

impl Downmixer {
    fn new(src_rate: u32, dst_rate: u32, channels: u16) -> Self {
        let step = if src_rate == 0 {
            1.0
        } else {
            src_rate as f64 / dst_rate.max(1) as f64
        };
        Downmixer { channels: channels.max(1), step, acc: 0.0 }
    }

    /// Feed one frame of interleaved float samples, returning the resampled
    /// mono output for the frames that should be emitted. All cpal sample
    /// formats (i16/u16/f32) convert to f32 floats, so we pin the associated
    /// type to `f32` to keep the summing concrete.
    fn push_frame<T: cpal::Sample<Float = f32>>(&mut self, frame: &[T]) -> Option<f32> {
        let sum: f32 = frame
            .iter()
            .take(self.channels as usize)
            .map(|s| s.to_float_sample())
            .sum();
        let mono = sum / self.channels as f32;
        self.acc += 1.0;
        if self.acc >= self.step {
            self.acc -= self.step;
            Some(mono)
        } else {
            None
        }
    }
}

struct SharedBuf {
    samples: Mutex<Vec<i16>>,
}

fn rms_of(samples: &[i16]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let mut sum = 0f64;
    for s in samples {
        let v = *s as f64 / 32768.0;
        sum += v * v;
    }
    (sum / samples.len() as f64).sqrt() as f32
}

/// Capture from the default microphone until trailing silence (or cancel/max).
fn capture_pcm(cancel: &AtomicBool, level_tx: &Sender<f32>) -> Result<CapturePcm, String> {
    let host = cpal::default_host();
    let device = host
        .default_input_device()
        .ok_or_else(|| "Microphone access is unavailable: no input device was found. Check that a microphone is connected and that PLUTO is allowed to record audio.".to_string())?;
    let supported = device
        .default_input_config()
        .map_err(|e| format!("Could not open the microphone: {}. Check that no other app is using it and that PLUTO has recording permission.", e))?;

    let src_rate = supported.sample_rate().0;
    let channels = supported.channels();
    let shared = Arc::new(SharedBuf { samples: Mutex::new(Vec::new()) });

    fn build_stream<T>(
        device: &cpal::Device,
        config: &cpal::StreamConfig,
        src_rate: u32,
        channels: u16,
        shared: Arc<SharedBuf>,
    ) -> Result<cpal::Stream, cpal::BuildStreamError>
    where
        T: cpal::SizedSample + cpal::Sample<Float = f32>,
    {
        let sink = shared.clone();
        // The downmixer lives across callbacks so the resampler phase is
        // preserved between audio chunks (no per-period drift at odd rates).
        let mut downmixer = Downmixer::new(src_rate, 16_000, channels);
        let err_cb = |err| eprintln!("[PLUTO mic] capture error: {err}");
        let data_cb = move |data: &[T], _: &cpal::InputCallbackInfo| {
            let mut out: Vec<i16> = Vec::with_capacity(data.len() / channels as usize);
            let mut frame_start = 0usize;
            while frame_start + channels as usize <= data.len() {
                let frame = &data[frame_start..frame_start + channels as usize];
                frame_start += channels as usize;
                if let Some(mono) = downmixer.push_frame(frame) {
                    let clamped = mono.clamp(-1.0, 1.0);
                    out.push((clamped * 32767.0) as i16);
                }
            }
            if !out.is_empty() {
                if let Ok(mut buf) = sink.samples.lock() {
                    buf.extend_from_slice(&out);
                }
            }
        };
        device.build_input_stream::<T, _, _>(config, data_cb, err_cb, None)
    }

    // Read the format before consuming `supported` (cpal 0.15 requires a
    // StreamConfig conversion that takes ownership).
    let sample_format = supported.sample_format();
    let config: cpal::StreamConfig = supported.into();
    let stream = match sample_format {
        cpal::SampleFormat::I16 => build_stream::<i16>(&device, &config, src_rate, channels, shared.clone()),
        cpal::SampleFormat::U16 => build_stream::<u16>(&device, &config, src_rate, channels, shared.clone()),
        cpal::SampleFormat::F32 => build_stream::<f32>(&device, &config, src_rate, channels, shared.clone()),
        other => {
            return Err(format!(
                "Microphone sample format {:?} is not supported by PLUTO.",
                other
            ))
        }
    }
    .map_err(|e| format!("Could not start microphone capture: {}. Check microphone permissions.", e))?;
    stream
        .play()
        .map_err(|e| format!("Could not start microphone capture: {}. Check microphone permissions.", e))?;

    let started = Instant::now();
    let mut samples: Vec<i16> = Vec::new();
    let mut spoke = false;
    let mut first_voice: Option<Instant> = None;
    let mut last_voice = Instant::now();
    let mut last_level_at = Instant::now() - Duration::from_millis(200);
    let mut smooth: f32 = 0.0;

    const LEADING_SILENCE_MS: u64 = 7_000; // wait this long for the user to start
    const TRAILING_SILENCE_MS: u64 = 1_000; // stop this long after speech ends
    const MAX_RECORD_MS: u64 = 20_000;
    const VOICE_RMS: f32 = 0.012; // ~ -38 dBFS threshold

    loop {
        if cancel.load(Ordering::SeqCst) {
            drop(stream);
            return Ok(CapturePcm { samples, spoke, cancelled: true });
        }
        let mut seg: Vec<i16> = Vec::new();
        {
            let mut buf = shared.samples.lock().unwrap_or_else(|p| p.into_inner());
            seg.append(&mut *buf);
        }
        if !seg.is_empty() {
            let rms = rms_of(&seg);
            smooth = if rms > smooth { rms } else { smooth * 0.85 };
            samples.extend_from_slice(&seg);
            if rms >= VOICE_RMS {
                let now = Instant::now();
                if !spoke {
                    first_voice = Some(now);
                }
                spoke = true;
                last_voice = now;
            }
        }
        let elapsed = started.elapsed().as_millis() as u64;
        if spoke && elapsed.saturating_sub(last_voice.duration_since(started).as_millis() as u64) >= TRAILING_SILENCE_MS {
            break;
        }
        if !spoke && elapsed >= LEADING_SILENCE_MS {
            break;
        }
        if elapsed >= MAX_RECORD_MS {
            break;
        }
        if last_level_at.elapsed() >= Duration::from_millis(90) {
            last_level_at = Instant::now();
            let _ = level_tx.send(smooth.clamp(0.0, 1.0));
        }
        std::thread::sleep(Duration::from_millis(25));
    }
    drop(stream);
    let _ = level_tx.send(0.0);
    if spoke && first_voice.is_some() {
        // Keep ~100 ms of pre-roll after the first detected voice so leading
        // consonants are not clipped.
        let first_ms = first_voice
            .map(|t| t.duration_since(started).as_millis() as usize)
            .unwrap_or(0)
            .saturating_sub(100);
        let cut = (first_ms.saturating_mul(16_000) / 1_000).min(samples.len());
        samples.drain(..cut);
    }
    Ok(CapturePcm { samples, spoke, cancelled: false })
}

/// Transcribe raw 16 kHz mono PCM captured from the microphone.
fn transcribe_audio_bytes(wav: &[u8]) -> ToolResult {
    let program = match whisper_program() {
        Some(p) => p,
        None => {
            return ToolResult::fail(
                "stt",
                format!("Speech-to-text engine is not installed. {}", whisper_hint()),
            )
        }
    };
    let model = match whisper_model_path() {
        Some(m) => m,
        None => {
            return ToolResult::fail(
                "stt",
                format!("No whisper model was found. {}", whisper_hint()),
            )
        }
    };
    let tmp = tmp_file("stt", "wav");
    if std::fs::write(&tmp, wav).is_err() {
        return ToolResult::fail("stt", "Could not write temporary audio file.");
    }
    let txt = tmp.with_extension("txt");
    let base = tmp.with_extension("");
    let _ = std::fs::remove_file(&txt);
    let args = [
        "-m",
        model.to_str().unwrap_or(""),
        "-f",
        tmp.to_str().unwrap_or(""),
        "-nt",
        "-of",
        base.to_str().unwrap_or(""),
    ];
    let result = match run_process(&program, &args, 120_000, &[]) {
        Ok((code, _, _err)) if code == 0 => {
            let content = std::fs::read_to_string(&txt).unwrap_or_default();
            let text = content.trim().to_string();
            let _ = std::fs::remove_file(&tmp);
            let _ = std::fs::remove_file(&txt);
            if text.is_empty() {
                ToolResult::ok("stt", "Heard no speech.").with_data(json!({ "text": "", "heard_speech": false }))
            } else {
                ToolResult::ok("stt", "Transcribed.").with_data(json!({ "text": text, "heard_speech": true }))
            }
        }
        Ok((_, _, err)) => {
            let _ = std::fs::remove_file(&tmp);
            let detail = String::from_utf8_lossy(&err).trim().to_string();
            let detail = detail.chars().take(300).collect::<String>();
            ToolResult::fail("stt", format!("Speech recognition failed: {}", if detail.is_empty() { "unknown error" } else { &detail }))
        }
        Err(e) => {
            let _ = std::fs::remove_file(&tmp);
            ToolResult::fail("stt", format!("Speech recognition failed: {}", e))
        }
    };
    result
}

/// Public: full native record-and-transcribe turn.
pub fn stt_record(cancel: &AtomicBool, level_tx: Sender<f32>) -> ToolResult {
    let pcm = match capture_pcm(cancel, &level_tx) {
        Ok(p) => p,
        Err(e) => return ToolResult::fail("stt_record", e),
    };
    drop(level_tx);
    if pcm.samples.is_empty() {
        return ToolResult::ok("stt_record", "No audio captured.").with_data(json!({
            "text": "", "heard_speech": false, "cancelled": pcm.cancelled,
        }));
    }
    if !pcm.spoke {
        return ToolResult::ok("stt_record", "No speech detected.").with_data(json!({
            "text": "", "heard_speech": false, "cancelled": pcm.cancelled,
        }));
    }
    // Ignore accidental blips shorter than ~250 ms of audio.
    if pcm.samples.len() < 4_000 {
        return ToolResult::ok("stt_record", "Speech was too short.").with_data(json!({
            "text": "", "heard_speech": false, "cancelled": pcm.cancelled,
        }));
    }
    let wav = wav_bytes(&pcm.samples, 16_000);
    let duration_ms = (pcm.samples.len() as u64 * 1_000) / 16_000;
    let mut result = transcribe_audio_bytes(&wav);
    if result.success {
        let heard = result.data.get("heard_speech").and_then(|v| v.as_bool()).unwrap_or(true);
        let text = result.data.get("text").and_then(|v| v.as_str()).unwrap_or("").to_string();
        result.data = json!({
            "tool": "stt_record",
            "text": text,
            "heard_speech": heard,
            "engine": "whisper.cpp",
            "cancelled": false,
            "duration_ms": duration_ms,
            "sample_rate": 16_000,
        });
    }
    result
}

/// Legacy STT entry point (bytes from a browser recorder). Converts WebM/Opus
/// via ffmpeg when available, otherwise expects WAV.
pub fn stt_transcribe(audio: &[u8], mime: &str) -> ToolResult {
    let mime = mime.to_lowercase();
    let bytes: Vec<u8> = if audio.starts_with(b"RIFF") || mime.contains("wav") || mime.contains("pcm") {
        audio.to_vec()
    } else {
        let tmp_in = tmp_file("stt_in", "");
        let tmp_out = tmp_file("stt_cvt", "wav");
        let _ = std::fs::write(&tmp_in, audio);
        match find_program("ffmpeg") {
            Some(ffmpeg) => {
                let args = [
                    "-y",
                    "-i",
                    tmp_in.to_str().unwrap_or(""),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    tmp_out.to_str().unwrap_or(""),
                ];
                let converted = match run_process(&ffmpeg, &args, 60_000, &[]) {
                    Ok((code, _, _)) if code == 0 => std::fs::read(&tmp_out).unwrap_or_default(),
                    _ => Vec::new(),
                };
                let _ = std::fs::remove_file(&tmp_in);
                let _ = std::fs::remove_file(&tmp_out);
                converted
            }
            None => {
                let _ = std::fs::remove_file(&tmp_in);
                let _ = std::fs::remove_file(&tmp_out);
                Vec::new()
            }
        }
    };
    if bytes.is_empty() {
        return ToolResult::fail("stt_transcribe", "Could not convert the recorded audio (ffmpeg is needed for non-WAV input).");
    }
    let mut result = transcribe_audio_bytes(&bytes);
    if result.success {
        let heard = result.data.get("heard_speech").and_then(|v| v.as_bool()).unwrap_or(true);
        let text = result.data.get("text").and_then(|v| v.as_str()).unwrap_or("").to_string();
        result.data = json!({ "tool": "stt_transcribe", "text": text, "heard_speech": heard });
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tts_never_panics() {
        // Engine availability varies by machine; the call must never panic and
        // always reports success (with audio or a browser fallback marker).
        let result = tts_synthesize("hello world");
        assert!(result.success);
        let engine = result.data.get("engine").and_then(|v| v.as_str()).unwrap_or("browser");
        assert!(["piper", "pico2wave", "espeak-ng", "espeak", "browser"].contains(&engine));
    }

    #[test]
    fn empty_text_is_an_error() {
        assert!(!tts_synthesize("   ").success);
    }

    #[test]
    fn wav_header_is_valid() {
        let samples: Vec<i16> = vec![0; 100];
        let wav = wav_bytes(&samples, 16_000);
        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(&wav[8..12], b"WAVE");
        assert_eq!(wav.len(), 44 + 200);
    }

    #[test]
    fn downmixer_downsamples() {
        let mut d = Downmixer::new(48_000, 16_000, 1);
        let mut out = 0usize;
        let frame = [0.5f32];
        for _ in 0..48_000 {
            if d.push_frame(&frame).is_some() {
                out += 1;
            }
        }
        assert_eq!(out, 16_000);
    }

    #[test]
    fn downmixer_averages_stereo() {
        let mut d = Downmixer::new(16_000, 16_000, 2);
        let frame = [-1.0f32, 1.0f32];
        let got = d.push_frame(&frame);
        assert!(got.is_some());
        assert!(got.unwrap().abs() < 0.001);
    }
}
