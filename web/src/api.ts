import type {
  AgentDetail,
  AgentsPage,
  LeasesPage,
  MessagesPage,
  Overview,
  ProjectDetail,
  ProjectOverviewDetail,
  TasksPage,
  VillageSnapshot,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(payload.error || `Request failed with status ${response.status}`, response.status);
  }
  return payload as T;
}

export function getSession(): Promise<{ ok: boolean; role: string }> {
  return request("/v1/console/session");
}

export function login(token: string): Promise<{ ok: boolean; role: string; expires_in: number }> {
  return request("/v1/console/session", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function logout(): Promise<{ ok: boolean }> {
  return request("/v1/console/session", { method: "DELETE" });
}

export function getOverview(): Promise<Overview> {
  return request("/v1/console/overview");
}

export function getVillage(): Promise<VillageSnapshot> {
  return request("/v1/console/village");
}

export function getProject(projectId: string): Promise<ProjectDetail> {
  return request(`/v1/console/projects/${encodeURIComponent(projectId)}`);
}

function projectViewPath(
  projectId: string,
  view: string,
  params: Record<string, string | number | null | undefined> = {},
): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") query.set(key, String(value));
  });
  const suffix = query.size ? `?${query.toString()}` : "";
  return `/v1/console/projects/${encodeURIComponent(projectId)}/${view}${suffix}`;
}

export function getProjectOverview(projectId: string): Promise<ProjectOverviewDetail> {
  return request(projectViewPath(projectId, "summary"));
}

export function getProjectAgents(
  projectId: string,
  params: { limit?: number; cursor?: string | null; filter?: string; query?: string } = {},
): Promise<AgentsPage> {
  return request(projectViewPath(projectId, "agents", { limit: params.limit || 50, cursor: params.cursor, filter: params.filter, q: params.query }));
}

export function getProjectTasks(
  projectId: string,
  params: { limit?: number; cursor?: string | null; filter?: string; query?: string } = {},
): Promise<TasksPage> {
  return request(projectViewPath(projectId, "tasks", { limit: params.limit || 50, cursor: params.cursor, filter: params.filter, q: params.query }));
}

export function getProjectBroadcasts(
  projectId: string,
  params: { limit?: number; cursor?: string | null; query?: string } = {},
): Promise<MessagesPage> {
  return request(projectViewPath(projectId, "broadcasts", { limit: params.limit || 50, cursor: params.cursor, q: params.query }));
}

export function getProjectLeases(
  projectId: string,
  params: { limit?: number; cursor?: string | null; filter?: string; query?: string } = {},
): Promise<LeasesPage> {
  return request(projectViewPath(projectId, "leases", { limit: params.limit || 50, cursor: params.cursor, filter: params.filter, q: params.query }));
}

export function getAgentDetail(
  projectId: string,
  agentId: string,
  params: { limit?: number; cursor?: string | null } = {},
): Promise<AgentDetail> {
  return request(projectViewPath(projectId, `agents/${encodeURIComponent(agentId)}`, { limit: params.limit || 20, cursor: params.cursor }));
}
