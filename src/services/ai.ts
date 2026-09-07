import { usePlutoStore } from "@/store/plutoStore";
import { PlutoState, ExecutionStep, ActionPreview, Activity } from "@/types";
import { speak, cancelSpeech } from "@/services/tts";
import { call, isTauriApp, onPlutoEvent, type PlutoEventBody } from "@/services/ipc";
import { localAssistant } from "@/services/localAssistant";

/** Shape of the events the Rust backend streams over Tauri IPC. */
export interface BackendEvent {
  type: string;
  session_id?: string;
  state?: string;
  task?: string;
  error?: string;
  text?: string;
  audio?: string | null;
  tts?: string;
  step?: ExecutionStep;
  preview?: ActionPreview;
  activity?: Activity;
  data?: Record<string, unknown> | null;
}

const READY_STATES: PlutoState[] = ["listening", "success", "idle", "error"];

export const aiService = {
  unlisten: null as (() => void) | null,
  listenersReady: false,

  /**
   * Subscribe to Rust backend events. In the Tauri app this replaces the old
   * WebSocket entirely - no ports, no localhost server.
   */
  async connectEvents(): Promise<void> {
    if (this.listenersReady) return;
    if (!isTauriApp()) {
      // Browser/dev preview: the local assistant still drives the UI.
      this.listenersReady = true;
      return;
    }
    const unlisten = await onPlutoEvent((event: PlutoEventBody) => {
      this.handleBackendEvent(event as unknown as BackendEvent);
    });
    if (unlisten) {
      this.unlisten = unlisten;
      this.listenersReady = true;
      console.log("✅ Connected to PLUTO Rust backend (Tauri IPC)");
    }
  },

  handleBackendEvent(data: BackendEvent): void {
    const store = usePlutoStore.getState();

    switch (data.type) {
      case "session":
        if (data.state && !store.isSpeaking) store.setState(data.state as PlutoState);
        break;

      case "silence":
        // User said "silence" - stop listening mode entirely.
        store.setVoiceEngaged(false);
        store.setListening(false);
        store.setState("idle");
        const silenceResponse = data.data?.response;
        if (typeof silenceResponse === "string") store.setAiResponse(silenceResponse);
        break;

      case "agent_state": {
        const nextState = data.state as PlutoState | undefined;
        if (nextState) {
          if (nextState === "listening" && store.isSpeaking) {
            // The real return-to-listening happens when audio finishes
            // (see tts.ts) so we don't yank the UI mid-utterance.
          } else {
            store.setState(nextState);
          }
          if (READY_STATES.includes(nextState)) {
            store.setExecuting(false);
            store.setCurrentTask(null);
          }
        }
        if (data.task && nextState && !READY_STATES.includes(nextState)) {
          store.setCurrentTask(data.task);
        }
        if (data.error) store.setErrorMessage(data.error);
        // Surface the on-device brain readout (intent + confidence + planned tools).
        if (data.data) {
          const d = data.data as {
            intent?: string;
            confidence?: number;
            recommended_tools?: string[];
            response?: string;
          };
          if (d.intent !== undefined || d.confidence !== undefined) {
            store.setIntent(
              d.intent ?? store.intent,
              typeof d.confidence === "number" ? d.confidence : store.confidence,
              d.recommended_tools ?? store.recommendedTools
            );
          }
          if (d.response) store.setAiResponse(d.response);
        }
        break;
      }

      case "execution_step":
        if (data.step) {
          const currentSteps = store.executionSteps;
          const existingIndex = currentSteps.findIndex((s) => s.id === data.step!.id);
          if (existingIndex >= 0) {
            store.updateExecutionStep(data.step.id, data.step.status);
          } else {
            store.setExecutionSteps([...currentSteps, data.step]);
          }
        }
        break;

      case "activity":
        if (data.activity) store.addActivity(data.activity);
        break;

      case "action_preview":
        if (data.preview) {
          if (data.preview.requiresConfirmation) {
            store.setConfirmationRequired(data.preview);
          } else {
            store.setActionPreview(data.preview);
          }
        }
        break;

      case "speak":
        store.setAiResponse(data.text ?? null);
        // Fire-and-forget: plays backend audio (local TTS) or browser TTS,
        // then returns the UI to LISTENING.
        if (data.text) void speak(data.text, data.audio ?? null, data.tts);
        break;

      case "error":
        store.setState("error");
        store.setExecuting(false);
        store.setErrorMessage(data.error || "An error occurred");
        break;
    }
  },

  async executeCommand(rawCommand: string): Promise<void> {
    const store = usePlutoStore.getState();
    const command = rawCommand.trim();
    if (!command) return;

    cancelSpeech(); // interrupt any previous spoken response

    // Reset previous task state.
    store.setErrorMessage(null);
    store.setActionPreview(null);
    store.setConfirmationRequired(null);
    store.setAiResponse(null);
    store.setCommand(command);
    store.setExecuting(true);
    store.setExecutionSteps([]);
    store.setSpeaking(false);

    if (!isTauriApp()) {
      // Browser preview: in-browser assistant (no server).
      await localAssistant.execute(command, (event) => this.handleBackendEvent(event));
      return;
    }

    try {
      await call("pluto_execute_command", { command });
    } catch (error) {
      console.error("❌ Command execution failed:", error);
      const msg = error instanceof Error ? error.message : String(error);
      store.setState("error");
      store.setExecuting(false);
      store.setErrorMessage(
        msg.includes("busy")
          ? "PLUTO is still busy with the previous command. Please wait."
          : `PLUTO backend error: ${msg}`
      );
    }
  },

  confirmAction(action: string): void {
    if (isTauriApp()) void call("pluto_confirm", { action });
    else localAssistant.confirmAction(action);
  },

  rejectAction(action: string): void {
    if (isTauriApp()) void call("pluto_reject", { action });
    else localAssistant.rejectAction(action);
  },

  cancelAction(): void {
    cancelSpeech();
    const store = usePlutoStore.getState();
    store.resetToIdle();
    if (isTauriApp()) void call("pluto_interrupt");
    else localAssistant.cancelAction();
  },

  resetSession(): void {
    const store = usePlutoStore.getState();
    store.resetToIdle();
    if (isTauriApp()) void call("pluto_reset");
  },
};
