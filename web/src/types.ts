export type Presence = "online" | "idle" | "offline";

export interface Workspace {
  id: string;
  name: string;
  relay: string;
}

export interface ProjectSummary {
  project_id: string;
  display_name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  agent_count: number;
  active_agent_count: number;
  online_agent_count: number;
  idle_agent_count: number;
  busy_agent_count: number;
  active_task_count: number;
  blocked_task_count: number;
  active_lease_count: number;
  message_count: number;
  broadcast_count: number;
  direct_message_count: number;
}

export interface TaskOwner {
  agent_id: string;
  handle: string | null;
  contact_code: string | null;
  runtime: string;
  status: string;
  heartbeat_at: string;
  presence: Presence;
  last_seen_at: string;
  last_seen_seconds: number;
}

export interface Task {
  task_id: string;
  project_id: string;
  title: string;
  summary: string | null;
  owner_agent_id: string | null;
  owner: TaskOwner | null;
  status: string;
  current_step: string | null;
  next_step: string | null;
  blocked_reason: string | null;
  blocked_by: string[];
  progress_percent: number | null;
  version: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface Agent {
  project_id: string;
  agent_id: string;
  handle: string | null;
  contact_code: string | null;
  name: string | null;
  user_name: string | null;
  user_slug: string | null;
  runtime: string;
  workspace: string | null;
  task_id: string | null;
  status: string;
  registered_at: string;
  heartbeat_at: string;
  presence: Presence;
  last_seen_at: string;
  last_seen_seconds: number;
  current_task: Task | null;
  active_lease_count: number;
  message_count: number;
}

export interface Message {
  message_id: string;
  project_id: string;
  thread_id: string;
  sender_agent_id: string | null;
  recipient_agent_id: string | null;
  sender_handle: string | null;
  recipient_handle: string | null;
  sender_runtime: string | null;
  message_type: string;
  body: string;
  acked_at: string | null;
  created_at: string;
  acked_count: number;
  audience_count: number;
}

export interface WorkspaceBroadcast extends Message {
  project_display_name: string;
}

export interface Lease {
  lease_id: string;
  project_id: string;
  resource_id: string;
  canonical_resource_id: string;
  mode: string;
  holder_agent_id: string | null;
  holder_handle: string | null;
  holder_runtime: string | null;
  reason: string | null;
  state: string;
  effective_state: string;
  fencing_epoch: number;
  acquired_at: string;
  expires_at: number;
  released_at: string | null;
}

export interface ActivityEvent {
  event_id: number;
  project_id: string;
  event_type: string;
  actor_agent_id: string | null;
  actor_handle: string | null;
  actor_runtime: string | null;
  resource_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface DayActivityEvent extends ActivityEvent {
  project_display_name: string | null;
}

export interface DayActivity {
  date: string;
  project_id: string | null;
  totals: {
    total: number;
    tasks: number;
    messages: number;
    leases: number;
    agents: number;
    other: number;
  };
  events: DayActivityEvent[];
}

export interface ActivityCalendarDay {
  date: string;
  total: number;
  tasks: number;
  messages: number;
  leases: number;
  agents: number;
  other: number;
}

export interface Overview {
  workspace: Workspace;
  projects: ProjectSummary[];
  totals: {
    projects: number;
    agents: number;
    registered_agents: number;
    active_agents: number;
    online_agents: number;
    idle_agents: number;
    active_tasks: number;
    blocked_tasks: number;
    active_leases: number;
    broadcasts: number;
    direct_messages: number;
  };
  recent_broadcasts: WorkspaceBroadcast[];
  activity_calendar: ActivityCalendarDay[];
  latest_event_id: number;
}

export interface VillageProject {
  project: ProjectSummary;
  agents: Agent[];
  recent_messages: Message[];
  has_more_agents: boolean;
}

export interface VillageSnapshot {
  workspace: Workspace;
  projects: VillageProject[];
  agent_limit_per_project: number;
  generated_at: string;
}

export interface PageMeta {
  limit: number;
  returned_count: number;
  has_more: boolean;
  next_cursor: string | null;
}

export interface ProjectOverviewDetail {
  project: ProjectSummary;
  agents: Agent[];
  tasks: Task[];
  broadcasts: Message[];
  activity: ActivityEvent[];
  activity_calendar: ActivityCalendarDay[];
}

export interface AgentsPage {
  project: ProjectSummary;
  agents: Agent[];
  page: PageMeta;
}

export interface TasksPage {
  project: ProjectSummary;
  tasks: Task[];
  page: PageMeta;
}

export interface MessagesPage {
  project: ProjectSummary;
  broadcasts: Message[];
  page: PageMeta;
}

export interface LeasesPage {
  project: ProjectSummary;
  leases: Lease[];
  page: PageMeta;
}

export interface AgentDetail {
  agent: Agent;
  direct_messages: {
    items: Message[];
    page: PageMeta;
  };
  leases: Lease[];
}

export interface ProjectDetail {
  project: ProjectSummary;
  agents: Agent[];
  tasks: Task[];
  messages: Message[];
  broadcasts: Message[];
  direct_messages: Message[];
  leases: Lease[];
  activity: ActivityEvent[];
}

export type ConsoleView = "overview" | "agents" | "tasks" | "broadcasts" | "resources";

export interface DirectoryProject {
  project_id: string;
  display_name: string;
  agent_count: number;
  active_agent_count: number;
}

export interface DirectoryUser {
  user_slug: string | null;
  user_name: string | null;
  agent_count: number;
  active_agent_count: number;
  online_agent_count: number;
  project_count: number;
  projects: DirectoryProject[];
  runtimes: string[];
  last_seen_at: string;
  last_seen_seconds: number;
}

export interface DirectoryAgent extends Agent {
  project_display_name: string;
}

export interface DirectoryProjectSummary extends ProjectSummary {
  user_count: number;
  user_names: string[];
  unattributed_agent_count: number;
}

export interface DirectorySnapshot {
  workspace: Workspace;
  users: DirectoryUser[];
  agents: DirectoryAgent[];
  projects: DirectoryProjectSummary[];
  totals: {
    projects: number;
    users: number;
    registered_agents: number;
    active_agents: number;
    unattributed_agents: number;
  };
  generated_at: string;
}
