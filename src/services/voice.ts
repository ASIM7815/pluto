import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "./ai";

const BACKEND_URL = "http://127.0.0.1:8765";

const sampleVoiceQueries = [
  "Open YouTube and play a great song",
  "Open WhatsApp and send Owais a message saying I'll reach at 7",
  "Open VS Code and start my project",
  "Create a folder called PLUTO inside my Projects directory",
  "Check system stats and optimize RAM usage",
  "Compose an email to Owais about the project meeting"
];

let isVoiceActive = false;
let queryIndex = 0;

export const voiceService = {
  startListening(): void {
    const store = usePlutoStore.getState();
    if (isVoiceActive) return;

    isVoiceActive = true;
    store.setListening(true);
    store.setState("listening");
    store.setTranscript("Listening...");

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
          this.stopListening(targetQuery);
        }, 800);
      }
    }, 120);
  },

  stopListening(finalText?: string): void {
    const store = usePlutoStore.getState();
    isVoiceActive = false;
    store.setListening(false);

    const command = finalText || store.currentCommand || store.transcript;
    if (command && command !== "Listening...") {
      aiService.executeCommand(command);
    } else {
      store.setState("idle");
      store.setTranscript("");
    }
  },

  toggleListening(): void {
    if (isVoiceActive) {
      this.stopListening();
    } else {
      this.startListening();
    }
  },

  // Text-to-Speech using ElevenLabs via backend
  async synthesizeSpeech(text: string): Promise<void> {
    try {
      console.log("🔊 Synthesizing speech:", text);
      
      const response = await fetch(`${BACKEND_URL}/api/voice/synthesize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text }),
      });

      if (response.ok) {
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        
        audio.onended = () => {
          URL.revokeObjectURL(audioUrl);
        };
        
        await audio.play();
        console.log("✅ Speech synthesis complete");
      } else {
        console.error("❌ TTS failed:", response.statusText);
      }
    } catch (error) {
      console.error("❌ TTS error:", error);
      console.log("⚠️ Make sure PLUTO backend is running on port 8765");
    }
  },

  async getAvailableVoices(): Promise<any[]> {
    try {
      const response = await fetch(`${BACKEND_URL}/api/voice/voices`);
      if (response.ok) {
        const data = await response.json();
        return data.voices || [];
      }
    } catch (error) {
      console.error("Error fetching voices:", error);
    }
    return [];
  }
};
