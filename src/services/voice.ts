import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "./ai";

const REST_BASE = "/api/backend";

const sampleVoiceQueries = [
  "Open YouTube and play a great song",
  "Open WhatsApp and send Owais a message saying I'll reach at 7",
  "Open VS Code and start my project",
  "Create a folder called PLUTO inside my Projects directory",
  "Check system stats and optimize RAM usage",
  "Compose an email to Owais about the project meeting",
];

let isVoiceActive = false;
let queryIndex = 0;
let recognition: any = null;
let recognitionSupported = false;

function detectRecognition(): boolean {
  if (typeof window === "undefined") return false;
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  return Boolean(SR);
}

export const voiceService = {
  startListening(): void {
    const store = usePlutoStore.getState();
    if (isVoiceActive) return;

    recognitionSupported = detectRecognition();
    isVoiceActive = true;
    store.setListening(true);
    store.setState("listening");
    store.setTranscript("Listening...");

    if (recognitionSupported) {
      // Real speech-to-text via Web Speech API.
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      recognition = new SR();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      let finalText = "";
      recognition.onresult = (event: any) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += transcript;
          else interim += transcript;
        }
        const shown = finalText || interim;
        store.setTranscript(shown);
        store.setCommand(shown);
      };
      recognition.onerror = () => {
        this.stopListening();
      };
      recognition.onend = () => {
        const cmd = finalText || store.transcript;
        this.stopListening(cmd);
      };
      try {
        recognition.start();
      } catch {
        this.stopListening();
      }
    } else {
      // Fallback: simulate typing a sample query so the demo keeps working when
      // the browser/iframe does not allow microphone access.
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
          setTimeout(() => this.stopListening(targetQuery), 800);
        }
      }, 110);
    }
  },

  stopListening(finalText?: string): void {
    const store = usePlutoStore.getState();
    isVoiceActive = false;
    store.setListening(false);

    if (recognition) {
      try {
        recognition.stop();
      } catch {
        // ignore
      }
      recognition = null;
    }

    const command = finalText || store.currentCommand || store.transcript;
    if (command && command !== "Listening..." && command.trim()) {
      aiService.executeCommand(command);
    } else {
      store.setState("idle");
      store.setTranscript("");
    }
  },

  toggleListening(): void {
    if (isVoiceActive) this.stopListening();
    else this.startListening();
  },

  // TTS via backend ElevenLabs (returns audio we can play; browser TTS is the
  // fallback handled in tts.ts when no audio is sent).
  async synthesizeSpeech(text: string): Promise<void> {
    try {
      console.log("🔊 Synthesizing speech:", text);
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
        console.log("✅ Speech synthesis complete");
      } else {
        // Fall back to browser TTS.
        await import("./tts").then((m) => m.speak(text, null));
      }
    } catch (error) {
      console.error("❌ TTS error:", error);
      await import("./tts").then((m) => m.speak(text, null));
    }
  },

  async getAvailableVoices(): Promise<any[]> {
    try {
      const response = await fetch(`${REST_BASE}/voice/voices`);
      if (response.ok) {
        const data = await response.json();
        return data.voices || [];
      }
    } catch (error) {
      console.error("Error fetching voices:", error);
    }
    return [];
  },
};
