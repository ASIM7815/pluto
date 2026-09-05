import { usePlutoStore } from "@/store/plutoStore";
import { ExecutionStep, ActionPreview, Activity } from "@/types";
import { tauriService } from "./tauri";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const aiService = {
  async executeCommand(rawCommand: string): Promise<void> {
    const store = usePlutoStore.getState();
    const command = rawCommand.trim();

    if (!command) return;

    // Reset previous states
    store.setErrorMessage(null);
    store.setActionPreview(null);
    store.setConfirmationRequired(null);
    store.setCommand(command);
    store.setExecuting(true);

    // Check for error simulation test
    if (command.toLowerCase().includes("error") || command.toLowerCase().includes("fail")) {
      await this.handleErrorSimulation(command);
      return;
    }

    // 1. UNDERSTANDING
    store.setState("understanding");
    store.setCurrentTask("Parsing natural language request...");
    await sleep(700);

    // 2. THINKING
    store.setState("thinking");
    store.setCurrentTask("Analyzing system permissions & OS capabilities...");
    await sleep(900);

    // Determine task category and steps
    const lower = command.toLowerCase();

    if (lower.includes("youtube") || lower.includes("song") || lower.includes("music") || lower.includes("play")) {
      await this.runYouTubePipeline(command);
    } else if (lower.includes("whatsapp") || lower.includes("owais") || lower.includes("message")) {
      await this.runWhatsAppPipeline(command);
    } else if (lower.includes("email") || lower.includes("mail")) {
      await this.runEmailPipeline(command);
    } else if (lower.includes("delete") || lower.includes("remove")) {
      await this.runDeleteConfirmationPipeline(command);
    } else if (lower.includes("folder") || lower.includes("create") || lower.includes("directory")) {
      await this.runFolderPipeline(command);
    } else if (lower.includes("vscode") || lower.includes("vs code") || lower.includes("code")) {
      await this.runVSCodePipeline(command);
    } else {
      await this.runGenericPipeline(command);
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
    const store = usePlutoStore.getState();
    store.setActionPreview(null);
    store.setState("executing");

    const steps = store.executionSteps;
    if (steps.length > 2) {
      store.updateExecutionStep(steps[2].id, "current");
      store.setCurrentTask("Dispatching email via SMTP gateway...");
      await sleep(800);
      store.updateExecutionStep(steps[2].id, "completed");
    }

    store.setState("success");
    store.setCurrentTask("Email successfully sent to owais@example.com");

    store.addActivity({
      id: `act-${Date.now()}`,
      title: "Email Sent",
      description: "Subject: Project Sync & Meeting to owais@example.com",
      timestamp: "Just now",
      status: "success",
      category: "message"
    });

    await sleep(2500);
    store.resetToIdle();
  },

  async runDeleteConfirmationPipeline(_command: string): Promise<void> {
    const store = usePlutoStore.getState();

    store.setState("planning");
    const confirmData: ActionPreview = {
      type: "file_delete",
      title: "Confirm Dangerous Action",
      content: "PLUTO wants to delete 24 temporary cache files in /home/user/.cache/pluto_temp.",
      fileCount: 24,
      path: "/home/user/.cache/pluto_temp",
      requiresConfirmation: true
    };
    store.setConfirmationRequired(confirmData);
  },

  async confirmFileDelete(): Promise<void> {
    const store = usePlutoStore.getState();
    store.setConfirmationRequired(null);
    store.setState("executing");

    const steps: ExecutionStep[] = [
      { id: "s1", label: "Scanning target directory", status: "completed" },
      { id: "s2", label: "Executing safe unlinks on 24 files", status: "current" },
      { id: "s3", label: "Reclaiming 1.4 GB disk space", status: "pending" }
    ];
    store.setExecutionSteps(steps);
    store.setCurrentTask("Unlinking files...");
    await sleep(800);

    store.updateExecutionStep("s2", "completed");
    store.updateExecutionStep("s3", "current");
    store.setCurrentTask("Reclaiming disk space...");
    await sleep(700);
    store.updateExecutionStep("s3", "completed");

    await tauriService.deleteFile("/home/user/.cache/pluto_temp");

    store.setState("success");
    store.setCurrentTask("Deleted 24 files safely");

    store.addActivity({
      id: `act-${Date.now()}`,
      title: "Deleted 24 Cache Files",
      description: "Reclaimed 1.4 GB storage in /home/user/.cache",
      timestamp: "Just now",
      status: "success",
      category: "file"
    });

    await sleep(2500);
    store.resetToIdle();
  },

  async runFolderPipeline(_command: string): Promise<void> {
    const store = usePlutoStore.getState();

    store.setState("planning");
    const steps: ExecutionStep[] = [
      { id: "s1", label: "Check permissions in ~/Projects", status: "pending" },
      { id: "s2", label: "Create directory 'PLUTO'", status: "pending" },
      { id: "s3", label: "Initialize git repo & project boilerplate", status: "pending" }
    ];
    store.setExecutionSteps(steps);
    await sleep(600);

    store.setState("executing");
    for (let i = 0; i < steps.length; i++) {
      store.updateExecutionStep(steps[i].id, "current");
      store.setCurrentTask(steps[i].label);
      await sleep(600);
      store.updateExecutionStep(steps[i].id, "completed");
    }

    await tauriService.createFolder("/home/user/Projects/PLUTO");

    store.setState("success");
    store.setCurrentTask("Folder created: ~/Projects/PLUTO");

    store.addActivity({
      id: `act-${Date.now()}`,
      title: "Created Folder /Projects/PLUTO",
      description: "Directory initialized and ready for development",
      timestamp: "Just now",
      status: "success",
      category: "file"
    });

    await sleep(2500);
    store.resetToIdle();
  },

  async runVSCodePipeline(_command: string): Promise<void> {
    const store = usePlutoStore.getState();

    store.setState("planning");
    const steps: ExecutionStep[] = [
      { id: "s1", label: "Locate VS Code executable", status: "pending" },
      { id: "s2", label: "Open workspace ~/Projects/PLUTO", status: "pending" },
      { id: "s3", label: "Restore active editor tabs", status: "pending" }
    ];
    store.setExecutionSteps(steps);
    await sleep(600);

    store.setState("executing");
    for (let i = 0; i < steps.length; i++) {
      store.updateExecutionStep(steps[i].id, "current");
      store.setCurrentTask(steps[i].label);
      await sleep(600);
      store.updateExecutionStep(steps[i].id, "completed");
    }

    await tauriService.openApplication("Visual Studio Code");

    store.setState("success");
    store.setCurrentTask("VS Code launched with PLUTO workspace");

    store.addActivity({
      id: `act-${Date.now()}`,
      title: "Launched VS Code",
      description: "Opened workspace /home/user/Projects/PLUTO",
      timestamp: "Just now",
      status: "success",
      category: "app"
    });

    await sleep(2500);
    store.resetToIdle();
  },

  async runGenericPipeline(command: string): Promise<void> {
    const store = usePlutoStore.getState();

    store.setState("planning");
    const steps: ExecutionStep[] = [
      { id: "s1", label: `Formulate plan for: "${command}"`, status: "pending" },
      { id: "s2", label: "Execute Linux system automation sequence", status: "pending" },
      { id: "s3", label: "Verify execution results & OS output", status: "pending" }
    ];
    store.setExecutionSteps(steps);
    await sleep(600);

    store.setState("executing");
    for (let i = 0; i < steps.length; i++) {
      store.updateExecutionStep(steps[i].id, "current");
      store.setCurrentTask(steps[i].label);
      await sleep(700);
      store.updateExecutionStep(steps[i].id, "completed");
    }

    store.setState("success");
    store.setCurrentTask("Action completed successfully");

    store.addActivity({
      id: `act-${Date.now()}`,
      title: `Executed: ${command.slice(0, 30)}...`,
      description: "Linux system task completed without errors",
      timestamp: "Just now",
      status: "success",
      category: "automation"
    });

    await sleep(2500);
    store.resetToIdle();
  },

  async handleErrorSimulation(command: string): Promise<void> {
    const store = usePlutoStore.getState();

    store.setState("understanding");
    await sleep(500);
    store.setState("thinking");
    await sleep(600);
    store.setState("executing");

    const steps: ExecutionStep[] = [
      { id: "s1", label: "Connecting to target service", status: "completed" },
      { id: "s2", label: "Attempting command execution", status: "error" }
    ];
    store.setExecutionSteps(steps);
    store.setState("error");
    store.setErrorMessage("Service unreachable: Target socket refused connection. Please ensure target process is running.");

    store.addActivity({
      id: `act-${Date.now()}`,
      title: "Command Failed",
      description: `Failed to execute "${command}": Connection refused`,
      timestamp: "Just now",
      status: "error",
      category: "system"
    });
  },

  cancelAction(): void {
    const store = usePlutoStore.getState();
    store.resetToIdle();
  }
};
