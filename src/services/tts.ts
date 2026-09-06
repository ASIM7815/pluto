import { usePlutoStore } from "@/store/plutoStore";

let currentAudio: HTMLAudioElement | null = null;
let speechToken = 0;

function decodeBase64Audio(base64: string): Blob {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: "audio/mpeg" });
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

/**
 * Speak a response. Prefers ElevenLabs audio (base64) when present, otherwise
 * falls back to the browser's built-in speechSynthesis so PLUTO always talks.
 * Returns when speech finishes (or immediately if unavailable).
 */
export async function speak(
  text: string,
  audioBase64?: string | null
): Promise<void> {
  const store = usePlutoStore.getState();
  store.setSpeaking(true);
  store.setState("speaking");

  try {
    if (audioBase64) {
      try {
        await playAudioBlob(decodeBase64Audio(audioBase64));
      } catch {
        await speakBrowser(text);
      }
    } else {
      await speakBrowser(text);
    }
  } finally {
    // Speech finished -> auto-return to LISTENING (continuous loop).
    usePlutoStore.getState().setSpeaking(false);
    usePlutoStore.getState().setState("listening");
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
