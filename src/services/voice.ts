import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "./ai";

const REST_BASE = "/api/backend";

// Demo queries used ONLY when the browser has no SpeechRecognition API at all.
// They drive the input box so the UI is testable; execution is still real and
// this mode never auto-restarts (no infinite microphone loop).
const sampleVoiceQueries = [
  "Open YouTube",
  "Search Iron Man",
  "Create a folder called PLUTO inside my Projects directory",
  "Check system status",
];

export interface VoiceInfo {
  voice_id: string;
  name?: string;
  labels?: Record<string, string>;
}

let isVoiceActive = false;
let recognition: SpeechRecognition | null = null;
let recognitionSupported = false;
let finishedThisSession = false; // guards double-stop from onerror/onend
let queryIndex = 0;

function getSpeechRecognitionCtor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

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

    const SR = getSpeechRecognitionCtor();
    recognitionSupported = SR !== null;
    isVoiceActive = true;
    finishedThisSession = false;
    store.setListening(true);
    store.setState("listening");
    store.setTranscript("Listening...");
    if (manual || store.voiceEngaged) {
      // The next auto-restart after speech depends on this flag.
      store.setVoiceEngaged(true);
    }

    if (SR) {
      // Real speech-to-text via the Web Speech API.
      const rec = new SR();
      recognition = rec;
      rec.continuous = false;
      rec.interimResults = true;
      rec.lang = "en-US";

      let finalText = "";
      rec.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const transcript = result[0].transcript;
          if (result.isFinal) finalText += transcript;
          else interim += transcript;
        }
        const shown = finalText || interim;
        store.setTranscript(shown);
        store.setCommand(shown);
      };
      rec.onerror = () => {
        if (!finishedThisSession) {
          finishedThisSession = true;
          this.stopListening(undefined, false);
        }
      };
      rec.onend = () => {
        if (!finishedThisSession) {
          finishedThisSession = true;
          const cmd = finalText || usePlutoStore.getState().transcript;
          this.stopListening(cmd || undefined, false);
        }
      };
      try {
        rec.start();
      } catch {
        finishedThisSession = true;
        this.stopListening(undefined, false);
      }
    } else {
      // Fallback: simulate a spoken query (mic not available in this browser).
      console.warn(
        "Web Speech API unavailable - PLUTO will simulate typed input for this session."
      );
      const targetQuery = sampleVoiceQueries[queryIndex % sampleVoiceQueries.length];
      queryIndex++;
      let charIdx = 0;
      const interval = setInterval(() => {
        if (!isVoiceActive) {
          clearInterval(interval);
          return;
        }
        charIdx += 3;
        const partial = targetQuery.slice(0, charIdx);
        store.setTranscript(partial);
        store.setCommand(partial);
        if (charIdx >= targetQuery.length) {
          clearInterval(interval);
          setTimeout(() => {
            if (!finishedThisSession) {
              finishedThisSession = true;
              this.stopListening(targetQuery, false);
            }
          }, 700);
        }
      }, 90);
    }
  },

  stopListening(finalText?: string, manual = false): void {
    const store = usePlutoStore.getState();
    if (!isVoiceActive && !finalText) return;
    isVoiceActive = false;
    store.setListening(false);

    if (recognition) {
      try {
        recognition.stop();
      } catch {
        // ignore - recognition already stopped
      }
      recognition = null;
    }

    if (manual) {
      // The user toggled the mic off - do not auto-restart later.
      store.setVoiceEngaged(false);
    }

    const command = (finalText || store.currentCommand || store.transcript || "").trim();
    if (command && command !== "Listening...") {
      store.setTranscript("");
      store.setCommand(command);
      void aiService.executeCommand(command);
    } else {
      store.setState("idle");
      store.setTranscript("");
    }
  },

  toggleListening(): void {
    const store = usePlutoStore.getState();
    if (isVoiceActive) {
      this.stopListening(undefined, true);
    } else {
      if (store.isSpeaking) return; // don't start while PLUTO is talking
      this.startListening(true);
    }
  },

  /** Called after a spoken response finishes: re-arm the mic if this session
   *  was voice-driven and real SpeechRecognition is available. */
  autoRestartListening(): void {
    const store = usePlutoStore.getState();
    if (!store.autoListen || !store.voiceEngaged) return;
    if (!recognitionSupported) return; // demo mode must never auto-loop
    if (store.isSpeaking || store.isExecuting || isVoiceActive) return;
    setTimeout(() => {
      const s = usePlutoStore.getState();
      if (!s.isSpeaking && !s.isExecuting && !isVoiceActive) {
        this.startListening(false);
      }
    }, 450);
  },

  // TTS via backend (ElevenLabs when configured; audio blob). Browser TTS is
  // handled in tts.ts when no audio is attached to a speak event.
  async synthesizeSpeech(text: string): Promise<void> {
    try {
      const response = await fetch(`${REST_BASE}/voice/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (response.ok) {
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        audio.onended = () => URL.revokeObjectURL(audioUrl);
        await audio.play();
      } else {
        await import("./tts").then((m) => m.speak(text, null));
      }
    } catch (error) {
      console.error("TTS error:", error);
      await import("./tts").then((m) => m.speak(text, null));
    }
  },

  async getAvailableVoices(): Promise<VoiceInfo[]> {
    try {
      const response = await fetch(`${REST_BASE}/voice/voices`);
      if (response.ok) {
        const data = (await response.json()) as { voices?: VoiceInfo[] };
        return data.voices || [];
      }
    } catch (error) {
      console.error("Error fetching voices:", error);
    }
    return [];
  },
};
