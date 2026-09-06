import { create } from "zustand";
import { PlutoState, Activity, ExecutionStep, ActionPreview } from "@/types";

interface PlutoStore {
  state: PlutoState;
  currentCommand: string;
  isListening: boolean;
  isExecuting: boolean;
  currentTask: string | null;
  activities: Activity[];
  executionSteps: ExecutionStep[];
  actionPreview: ActionPreview | null;
  confirmationRequired: ActionPreview | null;
  errorMessage: string | null;
  transcript: string;
  aiResponse: string | null;
  isSpeaking: boolean;

  setState: (state: PlutoState) => void;
  setCommand: (command: string) => void;
  setListening: (value: boolean) => void;
  setExecuting: (value: boolean) => void;
  setCurrentTask: (task: string | null) => void;
  setExecutionSteps: (steps: ExecutionStep[]) => void;
  updateExecutionStep: (stepId: string, status: ExecutionStep["status"]) => void;
  setActionPreview: (preview: ActionPreview | null) => void;
  setConfirmationRequired: (preview: ActionPreview | null) => void;
  setErrorMessage: (msg: string | null) => void;
  setTranscript: (text: string) => void;
  setAiResponse: (response: string | null) => void;
  setSpeaking: (value: boolean) => void;
  addActivity: (activity: Activity) => void;
  clearActivities: () => void;
  resetToIdle: () => void;
}

const initialActivities: Activity[] = [
  {
    id: "act-1",
    title: "Opened YouTube",
    description: "Searching for 'Lofi Chill Beats 2026'...",
    timestamp: "2 mins ago",
    status: "success",
    category: "app"
  },
  {
    id: "act-2",
    title: "Sent message to Owais",
    description: '"I\'ll reach at 7 PM for the project sync."',
    timestamp: "5 mins ago",
    status: "success",
    category: "message"
  },
  {
    id: "act-3",
    title: "Created new folder",
    description: "/home/user/Projects/PLUTO_v2",
    timestamp: "12 mins ago",
    status: "success",
    category: "file"
  },
  {
    id: "act-4",
    title: "Checked system status",
    description: "CPU 23% • RAM 41% • Storage 68%",
    timestamp: "18 mins ago",
    status: "info",
    category: "system"
  }
];

export const usePlutoStore = create<PlutoStore>((set) => ({
  state: "idle",
  currentCommand: "",
  isListening: false,
  isExecuting: false,
  currentTask: null,
  activities: initialActivities,
  executionSteps: [],
  actionPreview: null,
  confirmationRequired: null,
  errorMessage: null,
  transcript: "",
  aiResponse: null,
  isSpeaking: false,

  setState: (state) => set({ state }),
  setCommand: (currentCommand) => set({ currentCommand }),
  setListening: (isListening) => set({ isListening }),
  setExecuting: (isExecuting) => set({ isExecuting }),
  setCurrentTask: (currentTask) => set({ currentTask }),
  setExecutionSteps: (executionSteps) => set({ executionSteps }),
  updateExecutionStep: (stepId, status) =>
    set((s) => ({
      executionSteps: s.executionSteps.map((step) =>
        step.id === stepId ? { ...step, status } : step
      )
    })),
  setActionPreview: (actionPreview) => set({ actionPreview }),
  setConfirmationRequired: (confirmationRequired) => set({ confirmationRequired }),
  setErrorMessage: (errorMessage) => set({ errorMessage }),
  setTranscript: (transcript) => set({ transcript }),
  setAiResponse: (aiResponse) => set({ aiResponse }),
  setSpeaking: (isSpeaking) => set({ isSpeaking }),
  addActivity: (activity) =>
    set((s) => ({ activities: [activity, ...s.activities.slice(0, 19)] })),
  clearActivities: () => set({ activities: [] }),
  resetToIdle: () =>
    set({
      state: "idle",
      isListening: false,
      isExecuting: false,
      currentTask: null,
      executionSteps: [],
      actionPreview: null,
      confirmationRequired: null,
      errorMessage: null,
      transcript: "",
      aiResponse: null,
      isSpeaking: false
    })
}));
