import { usePlutoStore } from "@/store/plutoStore";

let currentAudio: HTMLAudioElement | null = null;
let speechToken = 0;
let playbackCancelled = false;

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
    if (playbackCancelled) {
      resolve(); // stopped before it even started
      return;
    }
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;
    let settled = false;
    const finish = (err?: Error) => {
      if (settled) return;
      settled = true;
      URL.revokeObjectURL(url);
      if (currentAudio === audio) currentAudio = null;
      if (err) reject(err);
      else resolve();
    };

    // IMPORTANT: onpause also fires when cancelSpeech() pauses the audio.
    // Without it, stopping PLUTO's voice left the UI stuck in "speaking".
    audio.onended = () => finish();
    audio.onpause = () => finish();
    audio.onerror = () => finish(new Error("audio playback failed"));
    // Some browsers need play() to be user-gesture-backed; catch rejection.
    audio.play().catch((e) => finish(e instanceof Error ? e : new Error(String(e))));
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
    // Always resolve (also on cancel) so the UI never hangs in "speaking".
    u.onend = () => resolve();
    u.onerror = () => resolve();
    if (playbackCancelled && token === speechToken) {
      resolve();
      return;
    }
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
 * PLUTO always talks. Resolves when speech finishes (or is stopped via
 * cancelSpeech) and then returns the UI to LISTENING for the next command.
 */
export async function speak(
  text: string,
  audioBase64?: string | null,
  ttsEngine?: string
): Promise<void> {
  const store = usePlutoStore.getState();
  playbackCancelled = false;
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
  playbackCancelled = true;
  speechToken++;
  if (currentAudio) {
    try {
      currentAudio.pause(); // fires onpause => playAudioBlob resolves
    } catch {
      // already stopped
    }
    currentAudio = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      // some browsers throw on cancel() with no active utterance
    }
  }
}
