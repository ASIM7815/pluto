import { usePlutoStore } from "@/store/plutoStore";

let currentAudio: HTMLAudioElement | null = null;
let speechToken = 0;

function decodeBase64Audio(base64: string, mime = "audio/mpeg"): Blob {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

function audioMimeForEngine(tts: string): string {
  // ElevenLabs and gTTS return MP3; the mock WAV fallback is wav.
  if (tts === "local_tts") return "audio/mpeg";
  if (tts === "elevenlabs") return "audio/mpeg";
  return "audio/mpeg";
}

function playAudioBlob(blob: Blob): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;

    const cleanup = () => URL.revokeObjectURL(url);

    audio.onended = () => {
      cleanup();
      resolve();
    };
    audio.onerror = () => {
      cleanup();
      // Fall back to browser TTS if audio fails to decode/play.
      reject(new Error("audio playback failed"));
    };
    // Some browsers need play() to be user-gesture-backed; catch rejection.
    audio.play().catch((e) => {
      cleanup();
      reject(e);
    });
  });
}

function speakBrowser(text: string): Promise<void> {
  return new Promise((resolve) => {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : null;
    if (!synth) {
      resolve();
      return;
    }
    const token = ++speechToken;
    synth.cancel(); // stop anything currently speaking
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.0;
    u.pitch = 1.0;
    u.lang = "en-US";
    u.onend = () => {
      if (token === speechToken) resolve();
    };
    u.onerror = () => {
      if (token === speechToken) resolve();
    };
    synth.speak(u);
  });
}

async function maybeRestartListening(): Promise<void> {
  const store = usePlutoStore.getState();
  if (!store.autoListen || !store.voiceEngaged || store.isSpeaking) return;
  // Re-arm the microphone a beat after the response ends so the user can just
  // keep talking. Only real SpeechRecognition is re-armed - the demo fallback
  // never auto-restarts (that would loop forever).
  await import("./voice").then((m) => m.voiceService.autoRestartListening());
}

/**
 * Speak a response. Prefers backend audio (ElevenLabs / local TTS) when
 * present, otherwise falls back to the browser's built-in speechSynthesis so
 * PLUTO always talks. Resolves when speech finishes (or immediately if speech
 * is unavailable) and then returns the UI to LISTENING for the next command.
 */
export async function speak(
  text: string,
  audioBase64?: string | null,
  ttsEngine?: string
): Promise<void> {
  const store = usePlutoStore.getState();
  store.setSpeaking(true);
  store.setState("speaking");

  try {
    if (audioBase64) {
      try {
        await playAudioBlob(decodeBase64Audio(audioBase64, audioMimeForEngine(ttsEngine || "")));
      } catch {
        await speakBrowser(text);
      }
    } else {
      await speakBrowser(text);
    }
  } finally {
    const s = usePlutoStore.getState();
    s.setSpeaking(false);
    s.setState("listening");
    // A finished task no longer occupies the execution panel.
    s.setExecuting(false);
    s.setCurrentTask(null);
    s.setTranscript("");
    await maybeRestartListening();
  }
}

export function cancelSpeech(): void {
  speechToken++;
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}
