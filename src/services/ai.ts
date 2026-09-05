import { usePlutoStore } from "@/store/plutoStore";
import { ExecutionStep, ActionPreview, Activity } from "@/types";

const BACKEND_URL = "http://127.0.0.1:8765";

export const aiService = {
  ws: null as WebSocket | null,
  reconnectAttempts: 0,
  maxReconnectAttempts: 5,

  connectWebSocket(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    console.log("🔌 Connecting to PLUTO backend...");
    
    try {
      this.ws = new WebSocket(`ws://127.0.0.1:8765/api/chat/ws`);

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
        
        // Auto-reconnect
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
      case "agent_state":
        if (data.state) store.setState(data.state);
        if (data.task) store.setCurrentTask(data.task);
        if (data.error) store.setErrorMessage(data.error);
        if (data.data?.response) {
          // Text response from LLM
          console.log("💬 Response:", data.data.response);
          store.setAiResponse(data.data.response);
        }
        break;

      case "execution_step":
        if (data.step) {
          const currentSteps = store.executionSteps;
          const existingIndex = currentSteps.findIndex(s => s.id === data.step.id);
          
          if (existingIndex >= 0) {
            store.updateExecutionStep(data.step.id, data.step.status);
          } else {
            store.setExecutionSteps([...currentSteps, data.step]);
          }
        }
        break;

      case "activity":
        if (data.activity) {
          store.addActivity(data.activity);
        }
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

    // Reset previous states
    store.setErrorMessage(null);
    store.setActionPreview(null);
    store.setConfirmationRequired(null);
    store.setAiResponse(null);
    store.setCommand(command);
    store.setExecuting(true);
    store.setExecutionSteps([]);

    // Connect WebSocket if not connected
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connectWebSocket();
      // Wait a bit for connection
      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    // Send command via WebSocket
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log("📤 Sending command:", command);
      this.ws.send(JSON.stringify({
        type: "command",
        command: command
      }));
    } else {
      // Fallback to REST API if WebSocket fails
      console.log("⚠️ WebSocket not ready, using REST API");
      await this.executeCommandREST(command);
    }
  },

  async executeCommandREST(command: string): Promise<void> {
    const store = usePlutoStore.getState();
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/chat/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ command }),
      });

      const result = await response.json();
      
      if (result.success) {
        store.setState(result.state);
        
        if (result.data?.response) {
          console.log("💬 Response:", result.data.response);
          store.setAiResponse(result.data.response);
        }

        store.addActivity({
          id: `act-${Date.now()}`,
          title: "Command Executed",
          description: result.message || command,
          timestamp: "Just now",
          status: "success",
          category: "automation"
        });

        setTimeout(() => store.resetToIdle(), 5000);
      } else {
        store.setState("error");
        store.setErrorMessage(result.message || "Command failed");
      }
    } catch (error) {
      console.error("❌ Command execution failed:", error);
      store.setState("error");
      store.setErrorMessage("Cannot connect to PLUTO backend. Make sure it's running on port 8765.");
    }
  },

  async runYouTubePipeline(_command: string): Promise<void> {
    const store = usePlutoStore.getState();

    // 3. PLANNING
    store.setState("planning");
    const steps: ExecutionStep[] = [
      { id: "s1", label: "Launch Chrome Browser", status: "pending" },
      { id: "s2", label: "Navigate to YouTube.com", status: "pending" },
      { id: "s3", label: "Search for 'Lofi Chill & Focus Beats'", status: "pending" },
      { id: "s4", label: "Select top high-quality audio stream", status: "pending" },
      { id: "s5", label: "Start playback and enter Fullscreen HUD mode", status: "pending" }
    ];
    store.setExecutionSteps(steps);
    await sleep(800);

    // 4. EXECUTING
    store.setState("executing");

    for (let i = 0; i < steps.length; i++) {
      const current = steps[i];
      store.updateExecutionStep(current.id, "current");
      store.setCurrentTask(current.label);
      await sleep(650);
      store.updateExecutionStep(current.id, "completed");
    }

    await tauriService.openURL("https://youtube.com/results?search_query=lofi+chill+beats");

    // 5. SUCCESS
    store.setState("success");
    store.setCurrentTask("YouTube playback active in fullscreen");

    const newActivity: Activity = {
      id: `act-${Date.now()}`,
      title: "Opened YouTube & Playing Song",
      description: "Started 'Lofi Chill & Focus Beats' in Chrome",
      timestamp: "Just now",
      status: "success",
      category: "app"
    };
    store.addActivity(newActivity);

    await sleep(2500);
    store.resetToIdle();
  },

  async runWhatsAppPipeline(_command: string): Promise<void> {
    const store = usePlutoStore.getState();

    store.setState("planning");
    const steps: ExecutionStep[] = [
      { id: "s1", label: "Connect to WhatsApp Web / Native Client", status: "pending" },
      { id: "s2", label: "Find contact 'Owais'", status: "pending" },
      { id: "s3", label: "Compose: \"I'll reach at 7 PM\"", status: "pending" },
      { id: "s4", label: "Dispatch message & verify delivery", status: "pending" }
    ];
    store.setExecutionSteps(steps);

    // Prepare Action Preview Card
    const preview: ActionPreview = {
      type: "message",
      title: "WhatsApp Message Preview",
      recipient: "Owais (+92 300 1234567)",
      content: "I'll reach at 7 PM for the project meeting.",
      requiresConfirmation: false
    };
    store.setActionPreview(preview);
    await sleep(1000);

    // EXECUTING
    store.setState("executing");
    for (let i = 0; i < steps.length; i++) {
      store.updateExecutionStep(steps[i].id, "current");
      store.setCurrentTask(steps[i].label);
      await sleep(700);
      store.updateExecutionStep(steps[i].id, "completed");
    }

    await tauriService.sendMessage("Owais", "I'll reach at 7 PM");

    store.setState("success");
    store.setCurrentTask("Message sent to Owais");

    store.addActivity({
      id: `act-${Date.now()}`,
      title: "WhatsApp Message Sent",
      description: 'To Owais: "I\'ll reach at 7 PM"',
      timestamp: "Just now",
      status: "success",
      category: "message"
    });

    await sleep(2500);
    store.resetToIdle();
  },

  async runEmailPipeline(_command: string): Promise<void> {
    const store = usePlutoStore.getState();

    store.setState("planning");
    const steps: ExecutionStep[] = [
      { id: "s1", label: "Parse recipient email address", status: "pending" },
      { id: "s2", label: "Draft email subject and body", status: "pending" },
      { id: "s3", label: "Awaiting user review & confirmation", status: "pending" }
    ];
    store.setExecutionSteps(steps);

    const emailPreview: ActionPreview = {
      type: "email",
      title: "Compose Email Draft",
      recipient: "owais@example.com",
      subject: "Project Sync & Meeting",
      content: "Hi Owais,\n\nI'll be available for the project review meeting at 7 PM today. Let me know if that works for you.\n\nBest,\nAsim",
      requiresConfirmation: true
    };
    store.setActionPreview(emailPreview);
  },

  async confirmEmailSend(): Promise<void> {
    // For confirmation actions, send via WebSocket
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "confirm",
        action: "email_send"
      }));
    }
  },

  async confirmFileDelete(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "confirm",
        action: "file_delete"
      }));
    }
  },

  cancelAction(): void {
    const store = usePlutoStore.getState();
    store.resetToIdle();
    
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "reset"
      }));
    }
  }
};
