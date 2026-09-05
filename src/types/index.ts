export type PlutoState =
  | "idle"
  | "listening"
  | "understanding"
  | "thinking"
  | "planning"
  | "executing"
  | "success"
  | "error";

export interface Activity {
  id: string;
  title: string;
  description: string;
  timestamp: string;
  status: "running" | "success" | "info" | "error";
  category?: "app" | "file" | "message" | "system" | "automation";
}

export interface ExecutionStep {
  id: string;
  label: string;
  status: "completed" | "current" | "pending" | "error";
  detail?: string;
}

export interface SystemMetrics {
  cpu: number;
  ram: number;
  storage: number;
  gpu?: number;
  temp?: number;
  networkUp?: string;
  networkDown?: string;
}

export interface QuickActionItem {
  id: string;
  label: string;
  iconName: string;
  command: string;
  description?: string;
}

export interface ActionPreview {
  type: "email" | "message" | "file_delete" | "command" | "automation";
  title: string;
  recipient?: string;
  subject?: string;
  content?: string;
  fileCount?: number;
  path?: string;
  meta?: Record<string, string>;
  requiresConfirmation: boolean;
}

export interface ProductivityCardItem {
  id: string;
  title: string;
  description: string;
  iconName: string;
  actionCommand: string;
}
