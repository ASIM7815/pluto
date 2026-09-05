import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "./ai";

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
  }
};
