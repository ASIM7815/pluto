import { usePlutoStore } from "@/store/plutoStore";
import { voiceService } from "@/services/voice";

export function useVoice() {
  const isListening = usePlutoStore((s) => s.isListening);
  const transcript = usePlutoStore((s) => s.transcript);

  const startListening = () => voiceService.startListening();
  const stopListening = () => voiceService.stopListening();
  const toggleListening = () => voiceService.toggleListening();

  return {
    isListening,
    transcript,
    startListening,
    stopListening,
    toggleListening
  };
}
