import { usePlutoStore } from "@/store/plutoStore";
import { voiceService } from "@/services/voice";

export function useVoice() {
  const isListening = usePlutoStore((s) => s.isListening);
  const transcript = usePlutoStore((s) => s.transcript);
  const voiceError = usePlutoStore((s) => s.voiceError);
  const voiceSupported = usePlutoStore((s) => s.voiceError === null);

  const startListening = () => voiceService.startListening();
  const stopListening = () => voiceService.stopListening();
  const toggleListening = () => voiceService.toggleListening();
  const clearVoiceError = () => usePlutoStore.getState().setVoiceError(null);

  return {
    isListening,
    transcript,
    voiceError,
    voiceSupported,
    startListening,
    stopListening,
    toggleListening,
    clearVoiceError
  };
}
