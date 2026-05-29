import type {
  AgentConfig,
  BeadsIssue,
  ChatMessage,
  ConfigPayload,
  NotesWorkspace,
  RuntimeStatus,
  SetupStatus,
  Subagent,
} from "./types";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  const response = await fetch(path, {
    ...options,
    headers,
    body,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail || detail;
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || "request failed");
  }

  return (await response.json()) as T;
}

export const api = {
  runtimeStatus() {
    return request<RuntimeStatus>("/api/runtime/status");
  },

  setupStatus() {
    return request<SetupStatus>("/api/config/setup-status");
  },

  config() {
    return request<ConfigPayload>("/api/config");
  },

  soulPreset(name: string) {
    return request<{ name: string; content: string }>(`/api/config/presets/${encodeURIComponent(name)}`);
  },

  models(apiBase: string, apiKey: string) {
    return request<{ models: string[]; error: string }>("/api/config/models", {
      method: "POST",
      body: { api_base: apiBase, api_key: apiKey },
    });
  },

  finishSetup(config: Partial<AgentConfig>, soul: string) {
    return request<{ ok: boolean; message: string }>("/api/config/setup", {
      method: "POST",
      body: { config, soul },
    });
  },

  subagents() {
    return request<{ subagents: Subagent[] }>("/api/subagents");
  },

  runSubagent(body: {
    session_id: string;
    type: string;
    description: string;
    prompt: string;
    emit_skill: boolean;
  }) {
    return request<{ ok: boolean; session_id: string; output: string }>("/api/subagents/run", {
      method: "POST",
      body,
    });
  },

  chat(message: string, sessionId: string) {
    return request<{ response: string; messages: ChatMessage[] }>("/api/chat", {
      method: "POST",
      body: { message, session_id: sessionId },
    });
  },

  getNotes(projectPath: string) {
    const params = new URLSearchParams({ project_path: projectPath });
    return request<{ workspace: NotesWorkspace }>(`/api/notes/workspace?${params}`);
  },

  saveNotes(projectPath: string, workspace: NotesWorkspace) {
    return request<{ ok: boolean }>("/api/notes/workspace", {
      method: "POST",
      body: { project_path: projectPath, workspace },
    });
  },

  beadsStatus(projectPath: string) {
    const params = new URLSearchParams({ project_path: projectPath });
    return request<{ initialized: boolean }>(`/api/beads/status?${params}`);
  },

  initBeads(projectPath: string) {
    return request<{ initialized: boolean; already_initialized?: boolean }>("/api/beads/init", {
      method: "POST",
      body: { project_path: projectPath },
    });
  },

  beadsIssues(projectPath: string) {
    const params = new URLSearchParams({ project_path: projectPath });
    return request<{ issues: BeadsIssue[] }>(`/api/beads/issues?${params}`);
  },

  createIssue(projectPath: string, title: string) {
    return request<{ issue: BeadsIssue }>("/api/beads/issues", {
      method: "POST",
      body: { project_path: projectPath, title },
    });
  },
};
