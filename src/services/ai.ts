import { usePlutoStore } from "@/store/plutoStore";
import { PlutoState, ExecutionStep, ActionPreview, Activity } from "@/types";
import { speak, cancelSpeech } from "@/services/tts";

// Use relative URLs so calls are proxied by the Next dev server to the
// FastAPI backend (works from any host, e.g. the sandbox preview).
const REST_BASE = "/api/backend";

// One stable session id per browser tab: it is sent to the WebSocket and to
// the REST fallback so the ContextManager keeps a single continuous session
// no matter which transport is used. It is generated on the client - PLUTO
// never hard-codes sessions.
function makeSessionId(): string {
  if (typeof window !== "undefined" && window.crypto?.randomUUID) {
    return `web-${window.crypto.randomUUID()}`;
  }
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
let SESSION_ID = "";

function getSessionId(): string {
  if (!SESSION_ID) SESSION_ID = makeSessionId();
  return SESSION_ID;
}

function wsUrl(): string {
  if (typeof window === "undefined") return "ws://127.0.0.1:8765/api/chat/ws";
  const configured = process.env.NEXT_PUBLIC_BACKEND_WS_URL;
  if (configured) {
    return `${configured.replace(/\/$/, "")}/api/chat/ws?session_id=${encodeURIComponent(getSessionId())}`;
  }

  // Route through the same public Next.js origin. This is essential for
  // remote/HTTPS previews, where the user's browser cannot reach localhost.
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/backend/chat/ws?session_id=${encodeURIComponent(
    getSessionId()
  )}`;
}

/** Shape of the events the backend streams (see app/schemas/chat.py). */
interface BackendEvent {
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
  data?: { response?: string } | null;
}

const READY_STATES: PlutoState[] = ["listening", "success", "idle", "error"];

export const aiService = {
  ws: null as WebSocket | null,
  reconnectAttempts: 0,
  maxReconnectAttempts: 5,

  connectWebSocket(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    if (this.ws?.readyState === WebSocket.CONNECTING) return;

    console.log("🔌 Connecting to PLUTO backend...");
    try {
      const ws = new WebSocket(wsUrl());
      this.ws = ws;

      ws.onopen = () => {
        console.log("✅ Connected to PLUTO backend");
        this.reconnectAttempts = 0;
      };

      ws.onmessage = (event) => {
        let data: BackendEvent;
        try {
          data = JSON.parse(String(event.data)) as BackendEvent;
        } catch {
          return;
        }
        this.handleBackendEvent(data);
      };

      ws.onerror = (event) => {
        console.error("❌ WebSocket error:", event);
      };

      ws.onclose = () => {
        console.log("🔌 Disconnected from backend");
        if (this.ws === ws) this.ws = null;
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          setTimeout(() => this.connectWebSocket(), 2000);
        }
      };
    } catch (error) {
      console.error("Failed to connect to backend:", error);
    }
  },

  waitForOpen(timeoutMs = 3500): Promise<boolean> {
    return new Promise((resolve) => {
      const started = Date.now();
      const poll = () => {
        if (this.ws?.readyState === WebSocket.OPEN) return resolve(true);
        if (Date.now() - started > timeoutMs) return resolve(false);
        setTimeout(poll, 120);
      };
      poll();
    });
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
        if (data.data?.response) store.setAiResponse(data.data.response);
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
        // Fire-and-forget: plays backend audio (ElevenLabs / local TTS) or
        // browser TTS, then returns the UI to LISTENING.
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

    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connectWebSocket();
      const opened = await this.waitForOpen(3500);
      if (!opened) {
        console.log("⚠️ WebSocket not available, using REST API");
        await this.executeCommandREST(command);
        return;
      }
    }

    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log("📤 Sending command:", command);
      this.ws.send(JSON.stringify({ type: "command", command }));
    } else {
      await this.executeCommandREST(command);
    }
  },

  async executeCommandREST(command: string): Promise<void> {
    const store = usePlutoStore.getState();
    try {
      const response = await fetch(`${REST_BASE}/chat/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, session_id: getSessionId() }),
      });
      const result = (await response.json()) as {
        success: boolean;
        message?: string;
        state?: string;
        data?: { response?: string };
      };

      if (result.success) {
        store.setState(result.state === "error" ? "error" : "success");
        const message = result.data?.response || result.message || command;
        store.setAiResponse(message);
        store.addActivity({
          id: `act-${Date.now()}`,
          title: "Command Executed",
          description: result.message || command,
          timestamp: "Just now",
          status: "success",
          category: "automation",
        });
        setTimeout(() => {
          usePlutoStore.getState().setExecuting(false);
          usePlutoStore.getState().setState("listening");
        }, 400);
      } else {
        store.setState("error");
        store.setExecuting(false);
        store.setErrorMessage(result.message || "Command failed");
        if (result.message) store.setAiResponse(result.message);
      }
    } catch (error) {
      console.error("❌ Command execution failed:", error);
      store.setState("error");
      store.setExecuting(false);
      store.setErrorMessage(
        "Cannot connect to PLUTO backend. Make sure it's running on port 8765."
      );
    }
  },

  confirmAction(action: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "confirm", action }));
    }
  },

  rejectAction(action: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "reject", action }));
    }
  },

  cancelAction(): void {
    cancelSpeech();
    const store = usePlutoStore.getState();
    store.resetToIdle();

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "interrupt" }));
    }
  },

  resetSession(): void {
    const store = usePlutoStore.getState();
    store.resetToIdle();
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({ type: "reset", clearHistory: true, session_id: getSessionId() })
      );
    }
  },
};
