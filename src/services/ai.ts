import { usePlutoStore } from "@/store/plutoStore";
import { ExecutionStep, ActionPreview, Activity } from "@/types";
import { speak, cancelSpeech } from "@/services/tts";

// Use relative URLs so calls are proxied by the Next dev server to the
// FastAPI backend (works from any host, e.g. the sandbox preview).
const REST_BASE = "/api/backend";

function wsUrl(): string {
  if (typeof window === "undefined") return "ws://127.0.0.1:8765/api/chat/ws";
  const proto = window.location.protocol === "https:" ? "wss://" : "ws://";
  return `${proto}${window.location.host}/api/backend/chat/ws`;
}

export const aiService = {
  ws: null as WebSocket | null,
  reconnectAttempts: 0,
  maxReconnectAttempts: 5,
  voiceRecognition: null as any,

  connectWebSocket(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    console.log("🔌 Connecting to PLUTO backend...");
    try {
      this.ws = new WebSocket(wsUrl());

      this.ws.onopen = () => {
        console.log("✅ Connected to PLUTO backend");
        this.reconnectAttempts = 0;
      };

      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        this.handleBackendEvent(data);
      };

      this.ws.onerror = (error) => {
        console.error("❌ WebSocket error:", error);
      };

      this.ws.onclose = () => {
        console.log("🔌 Disconnected from backend");
        this.ws = null;
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          setTimeout(() => this.connectWebSocket(), 2000);
        }
      };
    } catch (error) {
      console.error("Failed to connect to backend:", error);
    }
  },

  handleBackendEvent(data: any): void {
    const store = usePlutoStore.getState();

    switch (data.type) {
      case "silence":
        // User said "silence" - stop listening mode
        console.log("🔇 Silence mode activated");
        store.setListening(false);
        store.setState("idle");
        if (data.data?.response) {
          store.setAiResponse(data.data.response);
        }
        // Stop any active voice recognition
        if (this.voiceRecognition) {
          this.voiceRecognition.stop();
        }
        break;

      case "agent_state":
        if (data.state) {
          // Don't switch away from SPEAKING mid-utterance; tts.ts sets LISTENING
          // when the spoken response actually finishes.
          if (data.state === "listening" && store.isSpeaking) {
            break;
          }
          store.setState(data.state);
          // The loop returned to LISTENING -> the current task is done.
          if (data.state === "listening") {
            store.setExecuting(false);
            store.setCurrentTask(null);
          }
        }
        if (data.task && data.state !== "listening") store.setCurrentTask(data.task);
        if (data.error) store.setErrorMessage(data.error);
        if (data.data?.response) {
          console.log("💬 Response:", data.data.response);
          store.setAiResponse(data.data.response);
        }
        break;

      case "execution_step":
        if (data.step) {
          const currentSteps = store.executionSteps;
          const existingIndex = currentSteps.findIndex((s) => s.id === data.step.id);
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
        store.setAiResponse(data.text);
        // Fire-and-forget: plays ElevenLabs audio or browser TTS, then returns
        // the UI to LISTENING.
        if (data.text) speak(data.text, data.audio);
        break;

      case "error":
        store.setState("error");
        store.setErrorMessage(data.error || "An error occurred");
        break;
    }
  },

  async executeCommand(rawCommand: string): Promise<void> {
    const store = usePlutoStore.getState();
    const command = rawCommand.trim();
    if (!command) return;

    cancelSpeech(); // interrupt any previous spoken response

    // Reset previous states
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
      await new Promise((resolve) => setTimeout(resolve, 800));
    }

    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log("📤 Sending command:", command);
      this.ws.send(JSON.stringify({ type: "command", command }));
    } else {
      console.log("⚠️ WebSocket not ready, using REST API");
      await this.executeCommandREST(command);
    }
  },

  async executeCommandREST(command: string): Promise<void> {
    const store = usePlutoStore.getState();
    try {
      const response = await fetch(`${REST_BASE}/chat/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command }),
      });
      const result = await response.json();

      if (result.success) {
        store.setState(result.state);
        if (result.data?.response) {
          store.setAiResponse(result.data.response);
        }
        store.addActivity({
          id: `act-${Date.now()}`,
          title: "Command Executed",
          description: result.message || command,
          timestamp: "Just now",
          status: "success",
          category: "automation",
        });
        store.setState("listening");
      } else {
        store.setState("error");
        store.setErrorMessage(result.message || "Command failed");
      }
    } catch (error) {
      console.error("❌ Command execution failed:", error);
      store.setState("error");
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
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "reset", clearHistory: true }));
    }
  },
};
