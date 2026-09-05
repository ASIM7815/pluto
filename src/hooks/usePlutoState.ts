import { usePlutoStore } from "@/store/plutoStore";

export function usePlutoState() {
  const state = usePlutoStore((s) => s.state);
  const currentCommand = usePlutoStore((s) => s.currentCommand);
  const isListening = usePlutoStore((s) => s.isListening);
  const isExecuting = usePlutoStore((s) => s.isExecuting);
  const currentTask = usePlutoStore((s) => s.currentTask);
  const executionSteps = usePlutoStore((s) => s.executionSteps);
  const actionPreview = usePlutoStore((s) => s.actionPreview);
  const confirmationRequired = usePlutoStore((s) => s.confirmationRequired);
  const errorMessage = usePlutoStore((s) => s.errorMessage);
  const setState = usePlutoStore((s) => s.setState);
  const resetToIdle = usePlutoStore((s) => s.resetToIdle);

  return {
    state,
    currentCommand,
    isListening,
    isExecuting,
    currentTask,
    executionSteps,
    actionPreview,
    confirmationRequired,
    errorMessage,
    setState,
    resetToIdle
  };
}
