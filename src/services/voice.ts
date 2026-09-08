import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "./ai";
import { cancelSpeech } from "./tts";
import { call, isTauriApp } from "@/services/ipc";

export interface VoiceInfo {
  voice_id: string;
  name?: string;
  labels?: Record<string, string>;
}

/** Bare phrases that mean "stop what you're doing" (exact match only - a
 *  sentence like "stop the music" is still a normal command). */
const STOP_PHRASES = new Set([
  "stop", "stop it", "stop pluto", "cancel", "abort", "never mind", "nevermind",
  "quiet", "silence", "shut up", "stop talking", "stop speaking", "be quiet",
  "go to sleep", "sleep",
]);

const SPEECH_LANG = "en-US";
const END_OF_UTTERANCE_MS = 1400; // silence after speech => command complete
const RESTART_DELAY_MS = 250;
const MAX_NETWORK_RETRIES = 3;

type SrError =
  | "no-speech" | "aborted" | "not-allowed" | "service-not-allowed"
  | "audio-capture" | "network" | "bad-grammar" | "language-not-supported";

let isVoiceActive = false;
let recognition: SpeechRecognition | null = null;
let recognitionSupported = false;
let endOfUtteranceTimer: ReturnType<typeof setTimeout> | null = null;
let restartTimer: ReturnType<typeof setTimeout> | null = null;
let finalText = "";
let interimText = "";
let networkRetries = 0;
let sessionEpoch = 0; // invalidates callbacks from dead sessions

// Rust-side STT (used when the Web Speech API is unavailable/blocked).
let backendSttChecked = false;
let backendSttAvailable = false;

function getSpeechRecognitionCtor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

/** Report a voice problem so the UI can show it (never fail silently). */
function reportVoiceError(message: string, fatal = false): void {
  const store = usePlutoStore.getState();
  store.setVoiceError(message);
  if (fatal) {
    console.warn("[PLUTO voice]", message);
    store.setErrorMessage(message);
  }
}

function clearVoiceTimers(): void {
  if (endOfUtteranceTimer) {
    clearTimeout(endOfUtteranceTimer);
    endOfUtteranceTimer = null;
  }
  if (restartTimer) {
    clearTimeout(restartTimer);
    restartTimer = null;
  }
}

/** Decide what to do with a finished utterance. */
function dispatchCommand(rawText: string): void {
  const store = usePlutoStore.getState();
  const text = rawText.trim();
  if (!text) {
    store.setState("idle");
    return;
  }

  // Voice barge-in: "stop"/"cancel"/"quiet" aborts speech & the running task
  // instead of being executed as a command.
  const normalized = text.toLowerCase().replace(/[.!?,]+$/, "").trim();
  if (STOP_PHRASES.has(normalized)) {
    const taskRunning =
      store.isExecuting ||
      !["idle", "listening", "error", "success"].includes(store.state);
    if (taskRunning) {
      // A task is mid-flight: full interrupt (stops speech + IPC task).
      // The mic session itself stays engaged so the conversation continues.
      const wasEngaged = store.voiceEngaged;
      aiService.cancelAction();
      if (wasEngaged) {
        usePlutoStore.getState().setVoiceEngaged(true);
        setTimeout(() => voiceService.autoRestartListening(), 600);
      }
    } else if (store.isSpeaking) {
      // Only talking: just hush - the mic re-arms right after (continuous
      // listening keeps flowing).
      cancelSpeech();
      store.setState("listening");
    } else {
      store.setState("idle");
    }
    store.setVoiceError(null);
    return;
  }

  store.setTranscript("");
  store.setCommand(text);
  void aiService.executeCommand(text);
}

/** Tear the current listening session down (mic stays available). */
function teardownSession(): void {
  sessionEpoch++;
  clearVoiceTimers();
  isVoiceActive = false;
  if (recognition) {
    const rec = recognition;
    recognition = null;
    try {
      rec.onend = null;
      rec.onerror = null;
      rec.onresult = null;
      rec.stop();
    } catch {
      // already stopped
    }
  }
  stopRecorderSession();
  usePlutoStore.getState().setListening(false);
}

// ---------------------------------------------------------------------------
// Primary engine: Web Speech API (Chrome/Edge) with auto-restart watchdog
// ---------------------------------------------------------------------------
function startWebSpeech(epoch: number): void {
  const SR = getSpeechRecognitionCtor();
  if (!SR) return;

  const rec = new SR();
  recognition = rec;
  finalText = "";
  interimText = "";

  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = SPEECH_LANG;

  rec.onresult = (event) => {
    if (epoch !== sessionEpoch) return;
    networkRetries = 0; // we're receiving results => service healthy
    interimText = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      const text = result[0].transcript;
      if (result.isFinal) finalText += text;
      else interimText += text;
    }
    const shown = (finalText || interimText).trim();
    const s = usePlutoStore.getState();
    s.setTranscript(shown);
    s.setCommand(shown);

    // End-of-utterance detection: once the user pauses, run the command.
    if (endOfUtteranceTimer) clearTimeout(endOfUtteranceTimer);
    endOfUtteranceTimer = setTimeout(() => {
      if (epoch !== sessionEpoch) return;
      const utterance = (finalText || interimText).trim();
      if (utterance) {
        teardownSession();
        dispatchCommand(utterance);
      }
    }, END_OF_UTTERANCE_MS);
  };

  rec.onerror = (event) => {
    if (epoch !== sessionEpoch) return;
    const err = event.error as SrError;
    switch (err) {
      case "no-speech":
      case "aborted":
        // Benign: Chrome ended the turn after silence. Keep the mic alive.
        scheduleRestart(true);
        break;
      case "not-allowed":
      case "service-not-allowed":
        reportVoiceError(
          "Microphone access is blocked. Allow the microphone in your desktop environment, then press the mic button again.",
          true
        );
        usePlutoStore.getState().setVoiceEngaged(false);
        teardownSession();
        usePlutoStore.getState().setState("idle");
        break;
      case "audio-capture":
        reportVoiceError(
          "No microphone was found on this machine. Connect one (or check Input settings) and try again.",
          true
        );
        usePlutoStore.getState().setVoiceEngaged(false);
        teardownSession();
        usePlutoStore.getState().setState("idle");
        break;
      case "network":
        // Chrome's speech backend is unreachable. Retry a few times, then
        // fall back to Rust-side STT when PLUTO supports it.
        networkRetries++;
        if (networkRetries <= MAX_NETWORK_RETRIES) {
          scheduleRestart(true);
        } else if (backendSttChecked && backendSttAvailable) {
          reportVoiceError(
            "Browser speech service unreachable - switching to PLUTO's Rust transcription.",
            false
          );
          teardownSession();
          void startRecorderFallback();
        } else {
          reportVoiceError(
            "The browser speech service is unreachable (offline?). Check your internet connection and try again.",
            true
          );
          teardownSession();
          usePlutoStore.getState().setState("idle");
        }
        break;
      default:
        reportVoiceError(`Speech recognition error: ${err}`, false);
        scheduleRestart(true);
    }
  };

  rec.onend = () => {
    if (epoch !== sessionEpoch) return;
    // Chrome stops by itself every ~60s or after silence: transparently
    // restart while the session is voice-driven => continuous listening.
    if (isVoiceActive) scheduleRestart(true);
  };

  try {
    rec.start();
  } catch {
    // start() throws if already started - restart via the watchdog instead.
    scheduleRestart(true);
  }
}

/** Restart listening when nothing is pending (the continuous-listening
 *  watchdog). `silent` retries keep the session alive without spamming. */
function scheduleRestart(silent = false): void {
  const store = usePlutoStore.getState();
  if (!isVoiceActive && !silent) return;
  if (!store.autoListen && !silent) return;
  if (restartTimer) clearTimeout(restartTimer);
  restartTimer = setTimeout(() => {
    const s = usePlutoStore.getState();
    if (s.isSpeaking || s.isExecuting) return; // re-armed after the response
    if (s.voiceEngaged || silent) {
      voiceService.startListening(false);
    }
  }, RESTART_DELAY_MS);
}

// ---------------------------------------------------------------------------
// Fallback engine: MediaRecorder + Rust STT command
// ---------------------------------------------------------------------------
interface RecorderSession {
  recorder: MediaRecorder;
  stream: MediaStream;
  chunks: Blob[];
  audioCtx: AudioContext;
  raf: number | null;
  hardStop: ReturnType<typeof setTimeout>;
  epoch: number;
}
let recorderSession: RecorderSession | null = null;

async function ensureBackendStt(): Promise<boolean> {
  if (backendSttChecked) return backendSttAvailable;
  backendSttChecked = true;
  if (!isTauriApp()) return false;
  try {
    const data = await call<{ available?: boolean }>("pluto_stt_status");
    backendSttAvailable = Boolean(data.available);
  } catch {
    backendSttAvailable = false;
  }
  return backendSttAvailable;
}

function stopRecorderSession(): void {
  if (!recorderSession) return;
  const session = recorderSession;
  recorderSession = null;
  try {
    if (session.raf) cancelAnimationFrame(session.raf);
  } catch { /* noop */ }
  clearTimeout(session.hardStop);
  try {
    if (session.recorder.state !== "inactive") session.recorder.stop();
  } catch { /* noop */ }
  try {
    session.stream.getTracks().forEach((t) => t.stop());
  } catch { /* noop */ }
  try {
    void session.audioCtx.close();
  } catch { /* noop */ }
}

async function startRecorderFallback(): Promise<void> {
  const store = usePlutoStore.getState();
  const ok = await ensureBackendStt();
  if (!ok) {
    reportVoiceError(
      "Voice input is not supported by this browser and the Rust STT engine is not installed (install whisper-cli/whisper.cpp on PATH for offline transcription). Use Chrome/Edge for the Web Speech engine.",
      true
    );
    store.setVoiceEngaged(false);
    store.setState("idle");
    return;
  }

  if (!navigator.mediaDevices?.getUserMedia) {
    reportVoiceError("This browser cannot access the microphone.", true);
    store.setVoiceEngaged(false);
    store.setState("idle");
    return;
  }

  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    const denied = e instanceof DOMException && e.name === "NotAllowedError";
    reportVoiceError(
      denied
        ? "Microphone access is blocked. Allow the microphone for this app, then press the mic button again."
        : "Could not open the microphone. Check that no other app is using it.",
      true
    );
    store.setVoiceEngaged(false);
    store.setState("idle");
    return;
  }

  const epoch = ++sessionEpoch;
  const mimeType = MediaRecorder.isTypeSupported("audio/webm")
    ? "audio/webm"
    : "";
  const recorder = mimeType
    ? new MediaRecorder(stream, { mimeType })
    : new MediaRecorder(stream);
  const chunks: Blob[] = [];
  const audioCtx = new AudioContext();
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 512;
  audioCtx.createMediaStreamSource(stream).connect(analyser);

  const session: RecorderSession = {
    recorder, stream, chunks, audioCtx, raf: null, hardStop: null as never,
    epoch,
  };
  recorderSession = session;

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };
  recorder.onstop = () => {
    if (epoch !== sessionEpoch || !recorderSession) return;
    stopRecorderSession();
    const blob = new Blob(chunks, { type: mimeType || "audio/webm" });
    void transcribeBlob(blob, epoch);
  };

  recorder.start(250);

  // Simple VAD: watch the level, stop after speech + trailing silence.
  const buf = new Uint8Array(analyser.fftSize);
  let spoke = false;
  let lastVoiceAt = 0;
  const startedAt = performance.now();
  const SILENCE_AFTER_SPEECH_MS = 1500;
  const MAX_RECORD_MS = 12000;
  const LEADING_SILENCE_MS = 6000;

  const poll = () => {
    if (!recorderSession || recorderSession.epoch !== epoch) return;
    analyser.getByteTimeDomainData(buf);
    let peak = 0;
    for (let i = 0; i < buf.length; i++) {
      peak = Math.max(peak, Math.abs(buf[i] - 128));
    }
    const now = performance.now();
    if (peak > 10) {
      // signal above noise floor
      spoke = true;
      lastVoiceAt = now;
    }
    const timedOut =
      now - startedAt > MAX_RECORD_MS ||
      (spoke && now - lastVoiceAt > SILENCE_AFTER_SPEECH_MS) ||
      (!spoke && now - startedAt > LEADING_SILENCE_MS);
    if (timedOut) {
      if (spoke) {
        try { recorder.stop(); } catch { /* noop */ }
        return;
      }
      // Nothing spoken at all: restart the recorder window (keep listening).
      stopRecorderSession();
      scheduleRestart(true);
      return;
    }
    session.raf = requestAnimationFrame(poll);
  };
  session.raf = requestAnimationFrame(poll);
  session.hardStop = setTimeout(() => {
    if (recorderSession?.epoch === epoch && recorderSession.recorder.state !== "inactive") {
      try { recorderSession.recorder.stop(); } catch { /* noop */ }
    }
  }, MAX_RECORD_MS + 500);
}

async function transcribeBlob(blob: Blob, epoch: number): Promise<void> {
  const store = usePlutoStore.getState();
  try {
    const bytes = Array.from(new Uint8Array(await blob.arrayBuffer()));
    const data = await call<{ text?: string; heard_speech?: boolean }>(
      "pluto_stt_transcribe",
      { audio: bytes, mime: blob.type || "audio/webm" }
    );
    const text = (data.text || "").trim();
    if (epoch !== sessionEpoch) return;
    if (!text || !data.heard_speech) {
      // Silence / unintelligible: keep listening, don't punish the user.
      store.setState("idle");
      scheduleRestart(true);
      return;
    }
    store.setTranscript(text);
    dispatchCommand(text);
  } catch (e) {
    console.error("STT fallback error:", e);
    reportVoiceError("Voice transcription failed. Press the mic to try again.", false);
    store.setState("idle");
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
export const voiceService = {
  isRecognitionSupported(): boolean {
    return recognitionSupported;
  },

  isActive(): boolean {
    return isVoiceActive;
  },

  startListening(manual = true): void {
    const store = usePlutoStore.getState();
    if (isVoiceActive) return;
    // Never start the mic while PLUTO is executing or speaking.
    if (store.isSpeaking || store.isExecuting) return;

    clearVoiceTimers();
    const SR = getSpeechRecognitionCtor();
    recognitionSupported = SR !== null;
    isVoiceActive = true;
    networkRetries = 0;
    finalText = "";
    interimText = "";
    store.setVoiceError(null);
    store.setListening(true);
    store.setState("listening");
    store.setTranscript("Listening...");
    if (manual) store.setVoiceEngaged(true);

    if (SR) {
      startWebSpeech(++sessionEpoch);
    } else if (!(typeof window !== "undefined" && window.isSecureContext === false)) {
      // No Web Speech API (e.g. Tauri WebKit, Firefox): Rust STT fallback.
      void startRecorderFallback();
    } else {
      isVoiceActive = false;
      store.setListening(false);
      reportVoiceError(
        "Voice input requires a secure page (https or localhost). Open PLUTO in the Tauri app or enable HTTPS.",
        true
      );
      store.setState("idle");
    }
  },

  stopListening(finalTextOverride?: string, manual = false): void {
    const store = usePlutoStore.getState();
    const pending =
      (finalTextOverride || finalText || interimText || store.currentCommand || "")
        .replace(/^Listening\.\.\.$/, "")
        .trim();
    teardownSession();
    if (manual) {
      // The user toggled the mic off: end the voice session entirely.
      store.setVoiceEngaged(false);
      if (pending) dispatchCommand(pending);
      else store.setState("idle");
    } else if (pending) {
      dispatchCommand(pending);
    } else {
      store.setState("idle");
    }
  },

  toggleListening(): void {
    const store = usePlutoStore.getState();
    if (isVoiceActive) {
      this.stopListening(undefined, true);
    } else {
      if (store.isSpeaking) {
        // Mic button doubles as "stop talking" while PLUTO speaks.
        cancelSpeech();
        return;
      }
      this.startListening(true);
    }
  },

  /** Called after a spoken response finishes: re-arm the mic so the next
   *  command can be spoken without touching anything. */
  autoRestartListening(): void {
    const store = usePlutoStore.getState();
    if (!store.autoListen || !store.voiceEngaged) return;
    if (store.isSpeaking || store.isExecuting || isVoiceActive) return;
    if (!recognitionSupported && !(backendSttChecked && backendSttAvailable)) {
      // Rust fallback will be re-checked on demand; nothing to arm now.
      if (!recognitionSupported) return;
    }
    setTimeout(() => {
      const s = usePlutoStore.getState();
      if (!s.isSpeaking && !s.isExecuting && !isVoiceActive) {
        this.startListening(false);
      }
    }, 450);
  },

  /**
   * TTS via the Rust backend (espeak-ng / local voice; base64 audio).
   * Browser speechSynthesis is used when no audio is produced.
   */
  async synthesizeSpeech(text: string): Promise<void> {
    try {
      if (isTauriApp()) {
        const data = await call<{ audio_base64?: string; mime?: string; engine?: string }>(
          "pluto_tts_synthesize",
          { text }
        );
        if (data.audio_base64) {
          const audioUrl = URL.createObjectURL(
            new Blob([Uint8Array.from(atob(data.audio_base64), (c) => c.charCodeAt(0))], {
              type: data.mime || "audio/wav",
            })
          );
          const audio = new Audio(audioUrl);
          audio.onended = () => URL.revokeObjectURL(audioUrl);
          await audio.play();
          return;
        }
      }
      await import("./tts").then((m) => m.speak(text, null));
    } catch (error) {
      console.error("TTS error:", error);
      await import("./tts").then((m) => m.speak(text, null));
    }
  },

  async getAvailableVoices(): Promise<VoiceInfo[]> {
    try {
      if (isTauriApp()) {
        const data = await call<{ voices?: VoiceInfo[] }>("pluto_tts_voices");
        return data.voices || [];
      }
    } catch (error) {
      console.error("Error fetching voices:", error);
    }
    return [];
  },
};
