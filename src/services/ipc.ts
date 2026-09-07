/**
 * PLUTO IPC bridge.
 *
 * In the desktop app (Tauri + Rust) every OS action is a Tauri command.
 * In a plain browser (e.g. `npm run dev` preview) the same helpers fall back
 * to a small in-browser implementation so the UI stays fully interactive;
 * nothing ever needs a localhost server, Python or Node at runtime.
 */
import { invoke, isTauri as tauriRuntime } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export type PlutoEventBody = Record<string, unknown>;

let tauriChecked: boolean | null = null;

/** True when running inside the Tauri webview (Rust backend available). */
export function isTauriApp(): boolean {
  if (tauriChecked === null) {
    try {
      tauriChecked = typeof window !== "undefined" && tauriRuntime();
    } catch {
      tauriChecked = false;
    }
  }
  return tauriChecked;
}

/** Invoke a Rust command (no-op-safe in browser mode: throws). */
export async function call<T = unknown>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!isTauriApp()) {
    throw new Error(`[PLUTO IPC] ${cmd} is only available in the Tauri desktop app`);
  }
  return invoke<T>(cmd, args);
}

/** Subscribe to Rust backend events. Returns an unlisten function or null. */
export async function onPlutoEvent(
  handler: (event: PlutoEventBody) => void
): Promise<UnlistenFn | null> {
  if (!isTauriApp()) return null;
  try {
    return await listen<PlutoEventBody>("pluto-event", (e) => handler(e.payload));
  } catch (error) {
    console.error("[PLUTO IPC] failed to subscribe:", error);
    return null;
  }
}

/** File bytes for STT upload over IPC. */
export async function callBytes(
  cmd: string,
  args: Record<string, unknown>
): Promise<Uint8Array | null> {
  if (!isTauriApp()) return null;
  return invoke<Uint8Array>(cmd, args);
}
