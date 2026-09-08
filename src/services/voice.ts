import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "./ai";
import { cancelSpeech } from "./tts";
import { call, isTauriApp } from "@/services/ipc";

/**
 * PLUTO native voice input.
 *
 * The microphone is opened by the Rust backend (cpal) — no Web Speech API,
 * no getUserMedia, no HTTPS/localhost requirement. The Rust side runs a
 * lightweight energy VAD, streams live audio levels back as `audio_level`
 * events, and transcribes with whisper.cpp when it is installed. PLUTO works
 * (and reports clearly) when the STT engine or a microphone is missing.
 */

/** Bare phrases that mean "stop what you're doing" (exact match only). */
const STOP_PHRASES = new Set([
  "stop", "stop it", "stop pluto", "cancel", "abort", "never mind", "nevermind",
  "quiet", "silence", "shut up", "stop talking", "stop speaking", "be quiet",
  "go to sleep", "sleep",
]);

interface SttResult {
  text?: string;
  heard_speech?: boolean;
  cancelled?: boolean;
  engine?: string;
  duration_ms?: number;
}

let isVoiceActive = false; // a listening session is engaged
let recording = false; // the mic is currently capturing
let sessionEpoch = 0; // invalidates callbacks from dead sessions
let restarting = false;

/** Report a voice problem so the UI can show it (never fail silently). */
function reportVoiceError(message: string, fatal = false): void {
  const store = usePlutoStore.getState();
  store.setVoiceError(message);
  if (fatal) {
    console.warn("[PLUTO voice]", message);
    store.setErrorMessage(message);
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
      const wasEngaged = store.voiceEngaged;
      aiService.cancelAction();
      if (wasEngaged) {
        usePlutoStore.getState().setVoiceEngaged(true);
        setTimeout(() => voiceService.autoRestartListening(), 600);
      }
    } else if (store.isSpeaking) {
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

/** Ask the Rust backend to stop capturing right now. */
async function stopNativeCapture(): Promise<void> {
  try {
    if (isTauriApp()) await call("pluto_voice_cancel");
  } catch {
    // the capture may have finished on its own - that's fine
  }
}

/** One full record → transcribe turn against the Rust backend. */
async function recordUtterance(): Promise<void> {
  const store = usePlutoStore.getState();
  if (sessionEpoch === 0 || !store.voiceEngaged && !isVoiceActive) {
    return; // session torn down while we were starting
  }
  const epoch = sessionEpoch;
  recording = true;
  store.setListening(true);
  store.setState("listening");
  store.setTranscript("");
  store.setVoiceError(null);

  let result: SttResult | null = null;
  try {
    result = await call<SttResult>("pluto_stt_record");
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    if (epoch !== sessionEpoch) return;
    recording = false;
    store.setListening(false);
    // whisper.cpp missing is a clear, recoverable situation.
    if (/whisper|speech-to-text|speech recognition/i.test(message)) {
      reportVoiceError(
        "I can hear you, but no speech-to-text engine is installed. Install whisper.cpp and put a small ggml model in ~/.cache/pluto/ (see PLUTO status) to enable voice commands.",
        true
      );
    } else {
      reportVoiceError(
        message ||
          "Microphone access is unavailable. Check that a microphone is connected and that PLUTO has recording permission, then press the mic button again.",
        true
      );
    }
    store.setVoiceEngaged(false);
    store.setState("idle");
    return;
  }

  if (epoch !== sessionEpoch) return;
  recording = false;

  const text = (result?.text || "").trim();
  const heardSpeech = result?.heard_speech === true;

  if (result && result.cancelled && !heardSpeech) {
    // User pressed stop before saying anything meaningful.
    store.setListening(false);
    if (!store.voiceEngaged) store.setState("idle");
    else scheduleRestart();
    return;
  }
  if (!heardSpeech || !text) {
    // Silence / unintelligible: keep listening, don't punish the user.
    scheduleRestart();
    return;
  }

  store.setListening(false);
  store.setTranscript(text);
  isVoiceActive = false; // a command is now being handled
  dispatchCommand(text);
}

function scheduleRestart(): void {
  const store = usePlutoStore.getState();
  if (restarting) return;
  if (!store.voiceEngaged && !store.autoListen) {
    store.setListening(false);
    store.setState("idle");
    return;
  }
  restarting = true;
  setTimeout(() => {
    restarting = false;
    const s = usePlutoStore.getState();
    if (s.isSpeaking || s.isExecuting || recording || !isVoiceActive) return;
    if (s.voiceEngaged || s.autoListen) {
      void recordUtterance();
    }
  }, 400);
}

/** Tear the current listening session down (mic capture stops). */
function teardownSession(): void {
  sessionEpoch++;
  isVoiceActive = false;
  recording = false;
  void stopNativeCapture();
  usePlutoStore.getState().setListening(false);
  usePlutoStore.getState().setAudioLevel(0);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
export const voiceService = {
  isActive(): boolean {
    return isVoiceActive || recording;
  },

  /** Native microphone input is what PLUTO ships with. */
  isRecognitionSupported(): boolean {
    return isTauriApp();
  },

  startListening(manual = true): void {
    const store = usePlutoStore.getState();
    if (isVoiceActive || recording) return;
    // Never start the mic while PLUTO is executing or speaking.
    if (store.isSpeaking || store.isExecuting) return;

    if (!isTauriApp()) {
      reportVoiceError(
        "Voice input is available in the PLUTO desktop app. In this browser preview, type your commands instead.",
        true
      );
      store.setState("idle");
      return;
    }

    sessionEpoch++;
    isVoiceActive = true;
    recording = false;
    store.setVoiceError(null);
    store.setListening(true);
    store.setState("listening");
    store.setTranscript("");
    if (manual) store.setVoiceEngaged(true);
    void recordUtterance();
  },

  stopListening(_finalTextOverride?: string, manual = false): void {
    const store = usePlutoStore.getState();
    teardownSession();
    if (manual) {
      // The user toggled the mic off: end the voice session entirely.
      store.setVoiceEngaged(false);
      store.setState("idle");
    }
  },

  toggleListening(): void {
    const store = usePlutoStore.getState();
    if (isVoiceActive || recording) {
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
    if (store.isSpeaking || store.isExecuting || isVoiceActive || recording) return;
    setTimeout(() => {
      const s = usePlutoStore.getState();
      if (!s.isSpeaking && !s.isExecuting && !isVoiceActive && !recording) {
        this.startListening(false);
      }
    }, 450);
  },

  /** TTS via the Rust backend (piper/pico2wave/espeak-ng female; base64 WAV).
   *  Browser speechSynthesis is the final fallback when no audio is produced. */
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

  async getAvailableVoices(): Promise<{ voice_id: string; name?: string }[]> {
    try {
      if (isTauriApp()) {
        const data = await call<{ voices?: { voice_id: string; name?: string }[] }>("pluto_tts_voices");
        return data.voices || [];
      }
    } catch (error) {
      console.error("Error fetching voices:", error);
    }
    return [];
  },
};
