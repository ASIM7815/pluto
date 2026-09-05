/**
 * Tauri abstraction bridge for PLUTO Linux Desktop AI Assistant
 * Provides clean interfaces for OS actions. Currently returns mock responses in browser dev mode.
 */

export interface SystemStats {
  cpu: number;
  ram: number;
  storage: number;
  uptime: string;
}

export const tauriService = {
  async isTauriAvailable(): Promise<boolean> {
    if (typeof window !== "undefined" && "__TAURI_IPC__" in window) {
      return true;
    }
    return false;
  },

  async openApplication(appName: string): Promise<{ success: boolean; pid?: number; message: string }> {
    console.log(`[Tauri Bridge] Launching application: ${appName}`);
    return {
      success: true,
      pid: Math.floor(Math.random() * 9000) + 1000,
      message: `Successfully launched ${appName}`
    };
  },

  async openURL(url: string): Promise<{ success: boolean; message: string }> {
    console.log(`[Tauri Bridge] Opening URL in default browser: ${url}`);
    return {
      success: true,
      message: `Opened ${url}`
    };
  },

  async getSystemStats(): Promise<SystemStats> {
    return {
      cpu: Math.floor(18 + Math.random() * 12),
      ram: Math.floor(38 + Math.random() * 8),
      storage: 68,
      uptime: "4 hours 22 mins"
    };
  },

  async createFolder(path: string): Promise<{ success: boolean; path: string }> {
    console.log(`[Tauri Bridge] Creating directory: ${path}`);
    return {
      success: true,
      path
    };
  },

  async deleteFile(path: string): Promise<{ success: boolean; deletedCount: number }> {
    console.log(`[Tauri Bridge] Safe deletion request for: ${path}`);
    return {
      success: true,
      deletedCount: 1
    };
  },

  async listFiles(_dirPath: string): Promise<string[]> {
    return [
      "PLUTO",
      "desktop-agent.rs",
      "system_hooks.py",
      "config.json",
      "audio_stream.wav"
    ];
  },

  async setVolume(level: number): Promise<{ success: boolean; level: number }> {
    console.log(`[Tauri Bridge] Audio volume set to ${level}%`);
    return { success: true, level };
  },

  async sendMessage(recipient: string, text: string): Promise<{ success: boolean; messageId: string }> {
    console.log(`[Tauri Bridge] Dispatching message to ${recipient}: "${text}"`);
    return {
      success: true,
      messageId: `msg-${Date.now()}`
    };
  }
};
