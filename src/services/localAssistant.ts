/**
 * In-browser companion for the PLUTO UI.
 *
 * Used ONLY when running the Next.js UI outside the Tauri desktop shell
 * (e.g. `npm run dev` preview). It keeps every frontend interaction and
 * animation alive by simulating the assistant pipeline, and performs the
 * actions a browser can genuinely do (open URLs, clipboard). All real OS
 * work happens through the Rust backend in the Tauri app.
 */
import { usePlutoStore } from "@/store/plutoStore";
import { BackendEvent } from "./ai";

type Emit = (event: BackendEvent) => void;

function emitStep(emit: Emit, id: string, label: string, status: "current" | "completed" | "error", detail?: string): void {
  emit({ type: "execution_step", step: { id, label, status, detail } });
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function when(cond: boolean, a: string, b: string): string {
  return cond ? a : b;
}

async function openUrl(url: string): Promise<boolean> {
  try {
    const win = window.open(url, "_blank", "noopener");
    return !!win || true; // popup blockers may block; treat as success for UX
  } catch {
    return false;
  }
}

export const localAssistant = {
  pendingAction: null as { action: string; resolve: (ok: boolean) => void } | null,

  async execute(command: string, emit: Emit): Promise<void> {
    const store = usePlutoStore.getState();
    const text = command.toLowerCase();

    emit({
      type: "agent_state",
      state: "understanding",
      task: "Understanding your request...",
      data: { intent: "nlu", confidence: 0.9, recommended_tools: [] },
    });
    await sleep(400);
    emit({ type: "agent_state", state: "thinking", task: "Reasoning about your request...", data: {} });
    await sleep(350);

    const plan = this.plan(text);
    const intent = plan.steps[0]?.label || "conversation";
    store.setIntent(intent, 0.9, plan.steps.map((s) => s.tool));
    emit({
      type: "agent_state",
      state: "planning",
      task: `Planning ${plan.steps.length || 1} step(s)...`,
      data: { intent, confidence: 0.9, recommended_tools: plan.tools },
    });
    await sleep(350);

    if (plan.steps.length === 0) {
      emit({ type: "agent_state", state: "success", task: plan.answer, data: { response: plan.answer } });
      emit({ type: "speak", text: plan.answer, audio: null, tts: "browser" });
      emit({ type: "agent_state", state: "listening", task: "Ready for your next command." });
      store.setExecuting(false);
      return;
    }

    let ok = true;
    for (let i = 0; i < plan.steps.length; i++) {
      const step = plan.steps[i];
      emitStep(emit, `s${i}`, step.label, "current");
      await sleep(550);
      const result = await step.run();
      emitStep(emit, `s${i}`, step.label, result.ok ? "completed" : "error", result.detail);
      emit({
        type: "activity",
        activity: {
          id: `act-${Date.now()}-${i}`,
          title: step.label,
          description: result.detail || "Executed",
          timestamp: "Just now",
          status: result.ok ? "success" : "error",
          category: step.category,
        },
      });
      if (!result.ok) {
        ok = false;
        break;
      }
    }

    const answer = ok ? plan.answer : `I couldn't complete that in this preview: ${plan.error}. In the Tauri desktop app this runs on your real Linux machine.`;
    emit({ type: "agent_state", state: ok ? "success" : "error", task: answer, data: { response: answer }, error: ok ? undefined : answer });
    emit({ type: "speak", text: answer, audio: null, tts: "browser" });
    emit({ type: "agent_state", state: "listening", task: "Ready for your next command." });
    store.setExecuting(false);
  },

  confirmAction(_action: string): void {
    this.pendingAction?.resolve(true);
    this.pendingAction = null;
    usePlutoStore.getState().setConfirmationRequired(null);
  },

  rejectAction(_action: string): void {
    this.pendingAction?.resolve(false);
    this.pendingAction = null;
    usePlutoStore.getState().setConfirmationRequired(null);
  },

  cancelAction(): void {
    this.pendingAction?.resolve(false);
    this.pendingAction = null;
    usePlutoStore.getState().resetToIdle();
  },

  plan(text: string): {
    tools: string[];
    steps: Array<{ label: string; tool: string; category: "app" | "file" | "system" | "browser"; run: () => Promise<{ ok: boolean; detail?: string }> }>;
    answer: string;
    error: string;
  } {
    const t = text.toLowerCase();

    // URLs / websites
    if (t.includes("youtube") || (t.includes("play") && t.includes("song"))) {
      const q = t.includes("lofi") ? "lofi chill beats" : "";
      const url = q ? `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}` : "https://www.youtube.com";
      return this.result(
        ["open_url"],
        [{ label: `Open ${q ? "YouTube search" : "YouTube"}`, tool: "open_url", category: "browser", run: async () => ({ ok: await openUrl(url), detail: `Opened ${url}` }) }],
        q ? `Searched YouTube for '${q}', BOSS. (Desktop app uses the real browser.)` : `Opened YouTube, BOSS.`,
        "browser open failed"
      );
    }
    if (/(open|go to|visit|launch)\s+(.+)/.test(text) && !/(app|terminal|file|folder)/.test(t)) {
      const target = String(RegExp.$1).trim();
      const url = /^https?:\/\//.test(target) ? target : /^\w[\w.-]+\.\w{2,}$/.test(target) ? `https://${target}` : `https://www.google.com/search?q=${encodeURIComponent(target)}`;
      return this.result(
        ["open_url"],
        [{ label: `Open ${target}`, tool: "open_url", category: "browser", run: async () => ({ ok: await openUrl(url), detail: `Opened ${url}` }) }],
        `Opened ${target}, BOSS.`,
        "browser open failed"
      );
    }
    if (/(search|find)\s+(.+)/.test(text)) {
      const q = RegExp.$2.replace(/^(for|on)\s+/i, "").trim();
      const url = `https://www.google.com/search?q=${encodeURIComponent(q)}`;
      return this.result(
        ["browser_search"],
        [{ label: `Search '${q}'`, tool: "browser_search", category: "browser", run: async () => ({ ok: await openUrl(url), detail: `Opened search for ${q}` }) }],
        `Found results for '${q}', BOSS.`,
        "search failed"
      );
    }

    // Clipboard
    if (t.includes("clipboard")) {
      const isCopy = /(copy|put|set|save|store)/.test(t);
      if (isCopy) {
        const quoted = text.match(/["“'](.+?)["”']/);
        const payload = quoted ? quoted[1] : text.replace(/.*?clipboard/gi, "").replace(/^(to|on|into)/, "").trim();
        return this.result(
          ["copy_to_clipboard"],
          [{ label: "Copy to clipboard", tool: "copy_to_clipboard", category: "system", run: async () => {
            try {
              await navigator.clipboard?.writeText(payload || "PLUTO");
              return { ok: true, detail: `Copied "${payload || "PLUTO"}"` };
            } catch {
              return { ok: false, detail: "Clipboard unavailable" };
            }
          } }],
          "Copied to the clipboard, BOSS.",
          "clipboard failed"
        );
      }
      return this.result(
        ["get_clipboard"],
        [{ label: "Read clipboard", tool: "get_clipboard", category: "system", run: async () => {
          try {
            const value = await navigator.clipboard?.readText?.() ?? "";
            return { ok: true, detail: value ? `"${value.slice(0, 120)}"` : "Clipboard is empty" };
          } catch {
            return { ok: false, detail: "Clipboard read blocked (allow clipboard access)" };
          }
        } }],
        "Here's what's in your clipboard, BOSS.",
        "clipboard read failed"
      );
    }

    // Screenshot
    if (t.includes("screenshot") || t.includes("capture") || t.includes("screen grab")) {
      return this.result(
        ["take_screenshot"],
        [{ label: "Take screenshot", tool: "take_screenshot", category: "system", run: async () => ({ ok: false, detail: "Browser preview cannot capture the desktop" }) }],
        "Taking a screenshot, BOSS.",
        "screenshot not available in browser preview"
      );
    }

    // Files & folders
    if (/(create|make|new)\s+(a\s+)?(folder|directory)/.test(t)) {
      const name = text.match(/(?:called|named)\s+([^\s,]+)/)?.[1] || "PLUTO";
      return this.result(
        ["create_folder"],
        [{ label: `Create folder ${name}`, tool: "create_folder", category: "file", run: async () => ({ ok: true, detail: `Created folder "${name}" (simulated - real FS in desktop app)` }) }],
        `Created folder '${name}', BOSS.`,
        "folder creation failed"
      );
    }
    if (/(create|make|new|write)\s+.+(file|document)/.test(t)) {
      const name = text.match(/(?:called|named)\s+([^\s,]+)/)?.[1] || "notes.txt";
      return this.result(
        ["create_file"],
        [{ label: `Create file ${name}`, tool: "create_file", category: "file", run: async () => ({ ok: true, detail: `Created file "${name}" (simulated - real FS in desktop app)` }) }],
        `Created file '${name}', BOSS.`,
        "file creation failed"
      );
    }
    if (/(delete|remove)\s+/.test(t)) {
      const name = text.match(/(?:file|folder|cache)\s*([\w.-]+)/)?.[1] || "target";
      return this.result(
        ["delete_file"],
        [{ label: `Delete ${name}`, tool: "delete_file", category: "file", run: async () => ({ ok: true, detail: `Deleted ${name} (simulated)` }) }],
        `Deleted ${name}, BOSS.`,
        "delete failed"
      );
    }

    // System status
    if (/(system|status|metrics|cpu|ram|memory|disk)/.test(t)) {
      const cpu = Math.round(10 + Math.random() * 30);
      const ram = Math.round(30 + Math.random() * 30);
      return this.result(
        ["get_processes"],
        [{ label: "Check system status", tool: "get_processes", category: "system", run: async () => ({ ok: true, detail: `CPU ${cpu}% • RAM ${ram}%` }) }],
        `CPU ${cpu}% • RAM ${ram}% • All systems nominal, BOSS.`,
        "system check failed"
      );
    }

    // Greetings / help
    if (/^(hi|hello|hey|yo|sup|howdy)\b/.test(t)) {
      const answer = "Hello BOSS! I'm PLUTO, your autonomous Linux desktop assistant. I can open apps and websites, manage files, take screenshots, control volume and clipboard, and run commands. What do you need?";
      return { tools: [], steps: [], answer, error: "" };
    }
    if (t.includes("help") || t.includes("can you do") || t.includes("capabilities")) {
      const answer = "Here's what I can do, BOSS: open and close apps, browse and search, create/read/copy/move/delete files and folders, take screenshots, control volume and the clipboard, check running processes, and run terminal commands with your approval.";
      return { tools: [], steps: [], answer, error: "" };
    }
    if (t.includes("who are you")) {
      return { tools: [], steps: [], answer: "I'm PLUTO, your autonomous Linux desktop assistant. I run real tools on this machine - applications, browser automation, files, screenshots, system control.", error: "" };
    }

    const answer = `I understood that as a desktop command, BOSS. In this browser preview I can simulate it - the full ${this.detectIntent(t)} execution runs on your Linux machine through the Tauri app.`;
    return this.result(
      [this.detectIntent(t).replace(/ /g, "_")],
      [{ label: when(t.includes("open"), "Open target", "Execute task"), tool: "execute_command", category: "system", run: async () => ({ ok: true, detail: "Simulated in browser preview" }) }],
      answer,
      "preview only"
    );
  },

  detectIntent(t: string): string {
    if (t.includes("volume")) return "set volume";
    if (t.includes("app") || t.includes("open")) return "open application";
    if (t.includes("automation")) return "run automation";
    return "task";
  },

  result(
    tools: string[],
    steps: Array<{ label: string; tool: string; category: "app" | "file" | "system" | "browser"; run: () => Promise<{ ok: boolean; detail?: string }> }>,
    answer: string,
    error: string
  ) {
    return { tools, steps, answer, error };
  },
};
