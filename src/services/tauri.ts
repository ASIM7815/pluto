/**
 * PLUTO ↔ Rust (Tauri) bridge.
 *
 * Every method maps 1:1 to a Tauri command implemented in src-tauri (Rust).
 * In a plain browser these return the same browser behavior used before so
 * the dev preview keeps working.
 */
import { call, isTauriApp } from "@/services/ipc";

export interface SystemStats {
  cpu: number;
  ram: number;
  storage: number;
  uptime: string;
}

interface OpResult {
  success: boolean;
  message: string;
  pid?: number;
  data?: Record<string, unknown>;
}

export const tauriService = {
  async isTauriAvailable(): Promise<boolean> {
    return isTauriApp();
  },

  async openApplication(appName: string): Promise<OpResult> {
    if (!isTauriApp()) {
      console.log(`[PLUTO] (browser) launch: ${appName}`);
      return { success: true, message: `Launched ${appName} (simulated)` };
    }
    try {
      const data = await call<{ success: boolean; message: string; pid?: number }>(
        "pluto_launch_application",
        { application: appName, arguments: [] as string[] }
      );
      return data;
    } catch (e) {
      return { success: false, message: e instanceof Error ? e.message : String(e) };
    }
  },

  async openURL(url: string): Promise<OpResult> {
    if (!isTauriApp()) {
      window.open(url, "_blank", "noopener");
      return { success: true, message: `Opened ${url}` };
    }
    try {
      return await call<OpResult>("pluto_open_url", { url });
    } catch (e) {
      return { success: false, message: e instanceof Error ? e.message : String(e) };
    }
  },

  async getSystemStats(): Promise<SystemStats> {
    if (!isTauriApp()) {
      return {
        cpu: Math.floor(18 + Math.random() * 12),
        ram: Math.floor(38 + Math.random() * 8),
        storage: 68,
        uptime: "4 hours 22 mins",
      };
    }
    const s = await call<SystemStats>("pluto_get_system_stats");
    return s;
  },

  async createFolder(path: string): Promise<{ success: boolean; path: string }> {
    if (!isTauriApp()) return { success: true, path };
    return call("pluto_create_folder", { path });
  },

  async deleteFile(path: string): Promise<{ success: boolean; deletedCount: number }> {
    if (!isTauriApp()) return { success: true, deletedCount: 1 };
    return call("pluto_delete_file", { path });
  },

  async listFiles(dirPath: string): Promise<string[]> {
    if (!isTauriApp()) {
      return ["PLUTO", "pluto-core.rs", "config.json"];
    }
    const result = await call<{ items: Array<{ name: string; path: string; type: string }> }>(
      "pluto_list_directory",
      { path: dirPath }
    );
    return result.items.map((i) => `${i.type === "directory" ? "[DIR] " : ""}${i.name}`);
  },

  async setVolume(level: number): Promise<{ success: boolean; level: number }> {
    if (!isTauriApp()) return { success: true, level };
    return call("pluto_set_volume", { level });
  },

  async sendMessage(recipient: string, text: string): Promise<{ success: boolean; messageId: string }> {
    if (!isTauriApp()) return { success: true, messageId: `msg-${Date.now()}` };
    return call("pluto_send_message", { recipient, message: text });
  },

  async takeScreenshot(
    area = "full",
    directory?: string,
    filename?: string
  ): Promise<{ success: boolean; path?: string; message: string }> {
    if (!isTauriApp()) return { success: false, message: "Screenshots are available in the Tauri app" };
    return call("pluto_take_screenshot", { area, directory: directory ?? null, filename: filename ?? null });
  },
};
