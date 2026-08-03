import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Bot,
  Boxes,
  Check,
  ChevronRight,
  CircleDot,
  Gauge,
  Inbox,
  KeyRound,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  MessageSquareText,
  Radio,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
  Waypoints,
  X,
  type LucideIcon,
} from "lucide-react";
import { FormEvent, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  ApiError,
  getAgentDetail,
  getDayActivity,
  getDirectory,
  getOverview,
  getProjectAgents,
  getProjectBroadcasts,
  getProjectLeases,
  getProjectOverview,
  getProjectTasks,
  getSession,
  getVillage,
  login,
  logout,
} from "./api";
import type {
  ActivityCalendarDay,
  ActivityEvent,
  Agent,
  AgentDetail,
  AgentsPage,
  ConsoleView,
  DayActivity,
  DayActivityEvent,
  DirectoryAgent,
  DirectoryProjectSummary,
  DirectorySnapshot,
  DirectoryUser,
  Lease,
  LeasesPage,
  Message,
  MessagesPage,
  Overview,
  PageMeta,
  ProjectOverviewDetail,
  ProjectSummary,
  Task,
  TasksPage,
  VillageSnapshot,
  WorkspaceBroadcast,
} from "./types";

type WorkspaceView = "overview" | "directory";
type DirectoryMode = "projects" | "agents" | "people";

type WorkspaceFilter = "all" | "active_agents" | "active_tasks" | "blocked" | "broadcasts";
type AgentFilter = "active" | "all" | "online" | "idle" | "offline";
type TaskFilter = "all" | "active" | "blocked";
type ResourceFilter = "active" | "all";

const PROJECT_NAV_ITEMS: Array<{ id: ConsoleView; label: string; icon: LucideIcon }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "agents", label: "Agents", icon: Bot },
  { id: "tasks", label: "Tasks", icon: CircleDot },
  { id: "broadcasts", label: "Broadcasts", icon: MessageSquareText },
  { id: "resources", label: "Resources", icon: KeyRound },
];

const AgentVillage = lazy(() => import("./AgentVillage"));

function formatClock(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--";
  return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(date);
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(date);
}

function formatRelative(value: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (!Number.isFinite(seconds)) return "unknown";
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function sentenceCase(value: string): string {
  const result = value.replace(/[._-]+/g, " ");
  return result.charAt(0).toUpperCase() + result.slice(1);
}

function presenceName(presence: Agent["presence"]): string {
  return presence === "online" ? "Active" : sentenceCase(presence);
}

function agentLabel(agent: Agent | null | undefined): string {
  if (!agent) return "Unknown agent";
  return agent.handle ? `@${agent.handle}` : agent.name || agent.agent_id;
}

function taskTone(status: string): string {
  if (status === "completed") return "success";
  if (["blocked", "needs_human", "failed"].includes(status)) return "danger";
  if (status === "ready_for_review") return "warning";
  if (status === "cancelled") return "muted";
  return "active";
}

function isActiveTask(task: Task): boolean {
  return !["completed", "cancelled", "failed"].includes(task.status);
}

function agentWorkState(agent: Agent): string {
  if (agent.current_task) return sentenceCase(agent.current_task.status);
  if (agent.presence === "offline") return "Offline";
  if (agent.status === "busy") return "Busy";
  return agent.presence === "idle" ? "Idle" : "Available";
}

function eventTone(type: string): string {
  if (type.startsWith("lease.denied") || type.includes("failed")) return "danger";
  if (type.startsWith("lease")) return "warning";
  if (type.startsWith("message")) return "message";
  if (type.startsWith("task")) return "task";
  if (type.startsWith("agent")) return "agent";
  return "neutral";
}

function eventIcon(type: string): LucideIcon {
  if (type.startsWith("lease")) return LockKeyhole;
  if (type.startsWith("message")) return Send;
  if (type.startsWith("task")) return CircleDot;
  if (type.startsWith("agent")) return Bot;
  return Activity;
}

function eventSummary(event: ActivityEvent): string {
  const payload = event.payload;
  if (event.event_type === "message.sent") {
    return payload.recipient_agent_id ? "Sent a direct message" : "Published a project broadcast";
  }
  if (event.event_type === "message.acked") return "Acknowledged a message";
  if (event.event_type === "lease.granted") return `Acquired ${String(payload.resource_id || event.resource_id || "a resource")}`;
  if (event.event_type === "lease.released") return `Released ${String(payload.resource_id || event.resource_id || "a resource")}`;
  if (event.event_type === "lease.denied") return `Lease conflict on ${String(payload.resource_id || event.resource_id || "a resource")}`;
  if (event.event_type === "task.created") return `Started ${String(payload.title || "a task")}`;
  if (event.event_type === "task.updated") return `Moved task to ${sentenceCase(String(payload.status || "updated"))}`;
  if (event.event_type === "agent.registered") return "Joined this project";
  if (event.event_type === "agent.status_changed") return `Status changed to ${sentenceCase(String(payload.to || "updated"))}`;
  return sentenceCase(event.event_type);
}

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand-mark ${compact ? "brand-mark--compact" : ""}`} aria-label="Commons">
      <span className="brand-mark__disc" aria-hidden="true" />
      {!compact && <span>Commons</span>}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-badge--${taskTone(status)}`}>{sentenceCase(status)}</span>;
}

function PresenceLabel({ presence }: { presence: Agent["presence"] }) {
  return <span className={`presence-label presence-label--${presence}`}><span className={`presence-dot presence-dot--${presence}`} />{presenceName(presence)}</span>;
}

function AgentAvatar({ agent, size = "medium" }: { agent: Agent; size?: "small" | "medium" | "large" }) {
  const seed = (agent.handle || agent.name || agent.agent_id).replace(/[^a-zA-Z0-9]/g, "");
  const initials = seed.slice(0, 2).toUpperCase() || "AG";
  return (
    <span className={`agent-avatar agent-avatar--${size} agent-avatar--${agent.runtime}`} aria-hidden="true">
      {initials}
      <span className={`presence-dot presence-dot--${agent.presence}`} />
    </span>
  );
}

function LoadingScreen() {
  return (
    <main className="loading-screen" aria-label="Loading Commons Console">
      <BrandMark />
      <div className="loading-line" />
    </main>
  );
}

function LoginScreen({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) {
      setError("Enter the Team access token.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await login(token.trim());
      setToken("");
      onAuthenticated();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-shell" aria-labelledby="login-title">
        <div className="login-visual">
          <img src="/app/commons-architecture.png" alt="Intersecting modern walkways representing coordinated work" />
          <div className="login-visual__caption">
            <span className="signal-dot signal-dot--yellow" />
            Private coordination, visible in one place.
          </div>
        </div>
        <div className="login-panel">
          <BrandMark />
          <div className="login-copy">
            <p className="section-kicker">Private Relay Console</p>
            <h1 id="login-title">See how your agents work together.</h1>
            <p>Projects, agents, plans, messages, and shared-resource coordination across your private Relay.</p>
          </div>
          <form className="login-form" onSubmit={submit}>
            <label htmlFor="console-token">Team access token</label>
            <div className={`token-field ${error ? "token-field--error" : ""}`}>
              <ShieldCheck size={18} aria-hidden="true" />
              <input
                id="console-token"
                name="token"
                type="password"
                autoComplete="current-password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                aria-describedby={error ? "login-error" : undefined}
              />
            </div>
            {error && <p className="form-error" id="login-error">{error}</p>}
            <button className="primary-button" type="submit" disabled={submitting}>
              {submitting ? <RefreshCw className="spin" size={17} /> : <ArrowRight size={17} />}
              {submitting ? "Connecting" : "Open Console"}
            </button>
          </form>
          <p className="login-footnote"><LockKeyhole size={14} /> Token is exchanged for an HttpOnly session and is never stored in the browser.</p>
        </div>
      </section>
    </main>
  );
}

function MetricButton({
  label,
  value,
  detail,
  tone,
  icon: Icon,
  onClick,
  pressed = false,
}: {
  label: string;
  value: ReactNode;
  detail: string;
  tone: string;
  icon: LucideIcon;
  onClick: () => void;
  pressed?: boolean;
}) {
  return (
    <button className={`metric metric--${tone}`} type="button" onClick={onClick} aria-pressed={pressed} aria-label={`${label}: ${detail}`}>
      <span className="metric__top"><Icon size={16} /><span>{label}</span></span>
      <strong>{value}</strong>
      <span className="metric__detail"><span className="metric__detail-copy">{detail}</span><ArrowRight size={13} /></span>
    </button>
  );
}

function EmptyState({ icon: Icon, title, body }: { icon: LucideIcon; title: string; body: string }) {
  return (
    <div className="empty-state">
      <Icon size={24} />
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

function TaskProgress({ task }: { task: Task }) {
  if (task.progress_percent == null) return <span className="progress-unreported">Not reported</span>;
  return (
    <div className="progress" aria-label={`${task.progress_percent}% reported progress`}>
      <div className="progress__track"><span style={{ width: `${task.progress_percent}%` }} /></div>
      <span>{task.progress_percent}%</span>
    </div>
  );
}

function TaskRow({ task, onClick }: { task: Task; onClick?: () => void }) {
  return (
    <button className="task-row" type="button" onClick={onClick}>
      <span className={`task-row__marker task-row__marker--${taskTone(task.status)}`} />
      <span className="task-row__body">
        <span className="task-row__heading"><strong>{task.title}</strong><StatusBadge status={task.status} /></span>
        <span className="task-row__summary">{task.current_step || task.summary || "No current step reported"}</span>
        <span className="task-row__meta">
          <span>{task.owner?.handle ? `@${task.owner.handle}` : task.owner_agent_id || "Unassigned"}</span>
          <span>Updated {formatRelative(task.updated_at)}</span>
        </span>
      </span>
      <TaskProgress task={task} />
    </button>
  );
}

function AgentCard({ agent, onClick }: { agent: Agent; onClick: () => void }) {
  return (
    <button className="agent-card" type="button" onClick={onClick}>
      <span className="agent-card__identity">
        <AgentAvatar agent={agent} />
        <span><strong>{agentLabel(agent)}</strong><small>{agent.runtime} · {presenceName(agent.presence).toLowerCase()}</small></span>
      </span>
      <span className="agent-card__task">
        <strong>{agentWorkState(agent)}</strong>
        <span>{agent.current_task?.current_step || agent.current_task?.title || "No active task reported"}</span>
      </span>
      <span className="agent-card__footer">
        <span><KeyRound size={14} /> {agent.active_lease_count}</span>
        <span><MessageSquareText size={14} /> {agent.message_count}</span>
        <ArrowRight size={15} />
      </span>
    </button>
  );
}

function BroadcastPreview({ message, onClick, showProject = false }: { message: Message | WorkspaceBroadcast; onClick: () => void; showProject?: boolean }) {
  const projectName = "project_display_name" in message ? message.project_display_name : "Project broadcast";
  return (
    <button className="broadcast-preview" type="button" onClick={onClick}>
      <span className="broadcast-preview__icon"><Send size={16} /></span>
      <span className="broadcast-preview__body">
        <span><strong>{message.sender_handle ? `@${message.sender_handle}` : message.sender_agent_id || "Relay"}</strong><small>{showProject ? projectName : sentenceCase(message.message_type)}</small></span>
        <span>{message.body}</span>
        <small>{formatRelative(message.created_at)} · {message.acked_count}/{message.audience_count} acknowledged</small>
      </span>
      <ArrowRight size={15} />
    </button>
  );
}

function ProjectCard({ project, onClick }: { project: ProjectSummary; onClick: () => void }) {
  return (
    <button className="project-card" type="button" onClick={onClick}>
      <span className="project-card__heading">
        <span><Boxes size={17} /><strong>{project.display_name}</strong></span>
        <ArrowRight size={16} />
      </span>
      <span className="project-card__description">{project.description || "Private Relay project"}</span>
      <span className="project-card__ratio"><strong>{project.active_agent_count}</strong><span>/</span><strong>{project.agent_count}</strong><small>active / registered</small></span>
      <span className="project-card__stats">
        <span><CircleDot size={13} />{project.active_task_count} tasks</span>
        <span><MessageSquareText size={13} />{project.broadcast_count} broadcasts</span>
        <span><KeyRound size={13} />{project.active_lease_count} leases</span>
      </span>
      <span className="project-card__footer"><span>{project.blocked_task_count ? `${project.blocked_task_count} blocked` : "No blockers"}</span><time dateTime={project.last_activity_at}>{formatRelative(project.last_activity_at)}</time></span>
    </button>
  );
}

function scrollToProjects() {
  window.requestAnimationFrame(() => document.getElementById("workspace-projects")?.scrollIntoView({ behavior: "smooth", block: "start" }));
}

function WorkspaceOverview({
  overview,
  village,
  villageLoading,
  villageError,
  filter,
  query,
  onFilter,
  onProject,
  onAgent,
  onBroadcast,
}: {
  overview: Overview;
  village: VillageSnapshot | null;
  villageLoading: boolean;
  villageError: string;
  filter: WorkspaceFilter;
  query: string;
  onFilter: (filter: WorkspaceFilter) => void;
  onProject: (projectId: string) => void;
  onAgent: (projectId: string, agent: Agent) => void;
  onBroadcast: (message: WorkspaceBroadcast) => void;
}) {
  const projects = useMemo(() => {
    const next = overview.projects.filter((project) => `${project.display_name} ${project.project_id} ${project.description || ""}`.toLowerCase().includes(query));
    if (filter === "active_agents") return next.filter((project) => project.active_agent_count > 0).sort((a, b) => b.active_agent_count - a.active_agent_count);
    if (filter === "active_tasks") return next.filter((project) => project.active_task_count > 0).sort((a, b) => b.active_task_count - a.active_task_count);
    if (filter === "blocked") return next.filter((project) => project.blocked_task_count > 0).sort((a, b) => b.blocked_task_count - a.blocked_task_count);
    if (filter === "broadcasts") return next.filter((project) => project.broadcast_count > 0).sort((a, b) => b.broadcast_count - a.broadcast_count);
    return next;
  }, [filter, overview.projects, query]);

  function selectFilter(next: WorkspaceFilter) {
    onFilter(next);
    scrollToProjects();
  }

  return (
    <div className="view-stack workspace-overview">
      <Suspense fallback={<section className="agent-village agent-village--module-loading"><div className="agent-village__stage"><div className="agent-village__loading"><span /><span>Opening the floor...</span></div></div></section>}>
        <AgentVillage
          snapshot={village}
          fallbackProjects={overview.projects}
          loading={villageLoading}
          error={villageError}
          onProject={onProject}
          onAgent={onAgent}
        />
      </Suspense>

      <div className="metrics-row metrics-row--five" aria-label="Workspace summary">
        <MetricButton icon={Boxes} label="Projects" value={overview.totals.projects} detail="All Relay projects" tone="plain" onClick={() => selectFilter("all")} pressed={filter === "all"} />
        <MetricButton icon={Users} label="Active / registered" value={`${overview.totals.active_agents} / ${overview.totals.registered_agents}`} detail="Current / known Agents" tone="teal" onClick={() => selectFilter("active_agents")} pressed={filter === "active_agents"} />
        <MetricButton icon={Gauge} label="Active tasks" value={overview.totals.active_tasks} detail="Across workspace" tone="yellow" onClick={() => selectFilter("active_tasks")} pressed={filter === "active_tasks"} />
        <MetricButton icon={AlertTriangle} label="Blocked" value={overview.totals.blocked_tasks} detail="Needs coordination" tone="coral" onClick={() => selectFilter("blocked")} pressed={filter === "blocked"} />
        <MetricButton icon={MessageSquareText} label="Broadcasts" value={overview.totals.broadcasts} detail="Project-wide messages" tone="blue" onClick={() => selectFilter("broadcasts")} pressed={filter === "broadcasts"} />
      </div>

      <section className="content-section" id="workspace-projects" aria-labelledby="workspace-projects-title">
        <div className="section-heading">
          <div><h2 id="workspace-projects-title">Projects</h2><p>Every private coordination scope in this Relay workspace.</p></div>
          <span>{projects.length} shown</span>
        </div>
        {projects.length ? (
          <div className="project-grid">{projects.map((project) => <ProjectCard project={project} onClick={() => onProject(project.project_id)} key={project.project_id} />)}</div>
        ) : <EmptyState icon={Boxes} title="No projects in this view" body="Choose another summary metric to change the project filter." />}
      </section>

      <section className="content-section workspace-broadcasts" aria-labelledby="workspace-broadcasts-title">
        <div className="section-heading">
          <div><h2 id="workspace-broadcasts-title">Recent broadcasts</h2><p>Project-wide messages, separated from direct agent conversations.</p></div>
          <span>{overview.recent_broadcasts.length} recent</span>
        </div>
        {overview.recent_broadcasts.length ? (
          <div className="broadcast-preview-grid">{overview.recent_broadcasts.slice(0, 4).map((message) => <BroadcastPreview key={message.message_id} message={message} showProject onClick={() => onBroadcast(message)} />)}</div>
        ) : <EmptyState icon={Inbox} title="No broadcasts yet" body="Project broadcasts will appear here as agents publish plans and status updates." />}
      </section>
    </div>
  );
}

function userInitials(user: DirectoryUser): string {
  const source = (user.user_name || user.user_slug || "?").trim();
  const pieces = source.split(/[\s-]+/).filter(Boolean);
  if (!pieces.length) return "?";
  if (pieces.length === 1) return pieces[0].slice(0, 2).toUpperCase();
  return `${pieces[0][0]}${pieces[pieces.length - 1][0]}`.toUpperCase();
}

function DirectoryUserRow({ user, onProject }: { user: DirectoryUser; onProject: (projectId: string) => void }) {
  return (
    <tr>
      <td>
        <span className="directory-user">
          <span className={`directory-user__avatar ${user.user_slug ? "" : "directory-user__avatar--unknown"}`} aria-hidden="true">{userInitials(user)}</span>
          <span className="directory-user__identity">
            <strong>{user.user_name || "Unattributed"}</strong>
            <small>{user.user_slug ? `@${user.user_slug}-*` : "Legacy Agents without a Commons user"}</small>
          </span>
        </span>
      </td>
      <td>
        <span className="directory-project-chips">
          {user.projects.map((project) => (
            <button className="directory-project-chip" type="button" key={project.project_id} onClick={() => onProject(project.project_id)} title={`Open ${project.display_name}`}>
              <span className={project.active_agent_count ? "project-strip__signal project-strip__signal--active" : "project-strip__signal"} />
              {project.display_name}
              <small>{project.active_agent_count}/{project.agent_count}</small>
            </button>
          ))}
        </span>
      </td>
      <td className="directory-cell--count"><strong>{user.active_agent_count}</strong><span> / {user.agent_count}</span><small>active / registered</small></td>
      <td className="directory-cell--runtimes">{user.runtimes.map((runtime) => <span className="runtime-chip" key={runtime}>{runtime}</span>)}</td>
      <td className="directory-cell--seen">
        <span className={`presence-dot presence-dot--${user.active_agent_count ? "online" : "offline"}`} />
        {formatRelative(user.last_seen_at)}
      </td>
    </tr>
  );
}

function DirectoryAgentRow({ agent, onAgent, onProject }: { agent: DirectoryAgent; onAgent: (projectId: string, agent: Agent) => void; onProject: (projectId: string) => void }) {
  return (
    <tr>
      <td>
        <button className="directory-entity" type="button" onClick={() => onAgent(agent.project_id, agent)} title={`Open ${agentLabel(agent)}`}>
          <AgentAvatar agent={agent} size="small" />
          <span className="directory-user__identity">
            <strong>{agentLabel(agent)}</strong>
            <small>{agent.name || agent.agent_id}</small>
          </span>
        </button>
      </td>
      <td>
        <span className="directory-user__identity">
          <strong>{agent.user_name || "Unattributed"}</strong>
          <small>{agent.user_slug ? `@${agent.user_slug}-*` : "No Commons user recorded"}</small>
        </span>
      </td>
      <td>
        <button className="directory-project-chip" type="button" onClick={() => onProject(agent.project_id)} title={`Open ${agent.project_display_name}`}>
          <span className={agent.presence !== "offline" ? "project-strip__signal project-strip__signal--active" : "project-strip__signal"} />
          {agent.project_display_name}
        </button>
      </td>
      <td className="directory-cell--runtimes"><span className="runtime-chip">{agent.runtime}</span></td>
      <td className="directory-cell--seen">
        <span className="directory-presence">
          <PresenceLabel presence={agent.presence} />
          <small>{formatRelative(agent.last_seen_at)}</small>
        </span>
      </td>
    </tr>
  );
}

function DirectoryProjectRow({ project, onProject }: { project: DirectoryProjectSummary; onProject: (projectId: string) => void }) {
  return (
    <tr>
      <td>
        <button className="directory-entity" type="button" onClick={() => onProject(project.project_id)} title={`Open ${project.display_name}`}>
          <span className="directory-project-icon" aria-hidden="true"><Boxes size={16} /></span>
          <span className="directory-user__identity">
            <strong>{project.display_name}</strong>
            <small>{project.description || project.project_id}</small>
          </span>
        </button>
      </td>
      <td>
        <span className="directory-project-chips">
          {project.user_names.map((name) => <span className="people-chip" key={name}>{name}</span>)}
          {project.unattributed_agent_count > 0 && <span className="people-chip people-chip--muted">{project.unattributed_agent_count} unattributed</span>}
          {!project.user_names.length && !project.unattributed_agent_count && <span className="people-chip people-chip--muted">No participants</span>}
        </span>
      </td>
      <td className="directory-cell--count"><strong>{project.active_agent_count}</strong><span> / {project.agent_count}</span><small>active / registered</small></td>
      <td className="directory-cell--count"><strong>{project.active_task_count}</strong><span> active</span><small>{project.blocked_task_count ? `${project.blocked_task_count} blocked` : "no blockers"}</small></td>
      <td className="directory-cell--seen">
        <span className={`presence-dot presence-dot--${project.active_agent_count ? "online" : "offline"}`} />
        {formatRelative(project.last_activity_at)}
      </td>
    </tr>
  );
}

const DIRECTORY_MODES: Array<{ value: DirectoryMode; label: string }> = [
  { value: "projects", label: "Projects" },
  { value: "agents", label: "Agents" },
  { value: "people", label: "People" },
];

const DIRECTORY_COPY: Record<DirectoryMode, { title: string; description: string }> = {
  projects: { title: "Projects", description: "Every coordination scope on this Relay and the people participating in it." },
  agents: { title: "Agents", description: "Every registered Agent and the human who controls it." },
  people: { title: "People", description: "Everyone participating in this workspace, grouped from human-attributed Agent identity." },
};

function DirectoryView({
  directory,
  loading,
  error,
  query,
  onRetry,
  onProject,
  onAgent,
}: {
  directory: DirectorySnapshot | null;
  loading: boolean;
  error: string;
  query: string;
  onRetry: () => void;
  onProject: (projectId: string) => void;
  onAgent: (projectId: string, agent: Agent) => void;
}) {
  const [mode, setMode] = useState<DirectoryMode>("people");

  const users = useMemo(() => {
    if (!directory) return [];
    if (!query) return directory.users;
    return directory.users.filter((user) =>
      `${user.user_name || ""} ${user.user_slug || ""} ${user.runtimes.join(" ")} ${user.projects.map((project) => `${project.display_name} ${project.project_id}`).join(" ")}`
        .toLowerCase()
        .includes(query),
    );
  }, [directory, query]);

  const agents = useMemo(() => {
    if (!directory) return [];
    if (!query) return directory.agents;
    return directory.agents.filter((agent) =>
      `${agent.handle || ""} ${agent.name || ""} ${agent.agent_id} ${agent.user_name || ""} ${agent.user_slug || ""} ${agent.runtime} ${agent.project_display_name} ${agent.project_id}`
        .toLowerCase()
        .includes(query),
    );
  }, [directory, query]);

  const projects = useMemo(() => {
    if (!directory) return [];
    if (!query) return directory.projects;
    return directory.projects.filter((project) =>
      `${project.display_name} ${project.project_id} ${project.description || ""} ${project.user_names.join(" ")}`
        .toLowerCase()
        .includes(query),
    );
  }, [directory, query]);

  if (!directory) {
    if (loading) return <div className="content-skeleton" aria-label="Loading workspace directory" aria-busy="true"><span /><span /><span /></div>;
    return (
      <div className="view-stack">
        <EmptyState icon={AlertTriangle} title="Directory unavailable" body={error || "Retry the directory request."} />
        <button className="primary-button" type="button" onClick={onRetry}><RefreshCw size={16} /> Retry</button>
      </div>
    );
  }

  const copy = DIRECTORY_COPY[mode];
  const shownCount = mode === "people" ? users.length : mode === "agents" ? agents.length : projects.length;

  return (
    <div className="view-stack directory-overview">
      <div className="metrics-row" aria-label="Directory summary">
        <MetricButton icon={Boxes} label="Projects" value={directory.totals.projects} detail="Coordination scopes on this Relay" tone="plain" onClick={() => setMode("projects")} pressed={mode === "projects"} />
        <MetricButton icon={Users} label="People" value={directory.totals.users} detail="Humans attributed to Agents" tone="teal" onClick={() => setMode("people")} pressed={mode === "people"} />
        <MetricButton icon={Bot} label="Active / registered" value={`${directory.totals.active_agents} / ${directory.totals.registered_agents}`} detail="Agents across all projects" tone="yellow" onClick={() => setMode("agents")} pressed={mode === "agents"} />
        <MetricButton icon={AlertTriangle} label="Unattributed" value={directory.totals.unattributed_agents} detail="Legacy Agents without a user" tone="coral" onClick={() => setMode("agents")} pressed={false} />
      </div>

      <section className="content-section" aria-labelledby="directory-table-title">
        <div className="section-heading">
          <div><h2 id="directory-table-title">{copy.title}</h2><p>{copy.description}</p></div>
          <span>{shownCount} shown</span>
        </div>
        <div className="view-toolbar">
          <FilterTabs label="Directory view" value={mode} options={DIRECTORY_MODES} onChange={setMode} />
        </div>
        {mode === "people" && (users.length ? (
          <div className="directory-table-wrap">
            <table className="directory-table">
              <thead>
                <tr><th scope="col">User</th><th scope="col">Projects</th><th scope="col">Agents</th><th scope="col">Runtimes</th><th scope="col">Last seen</th></tr>
              </thead>
              <tbody>
                {users.map((user) => <DirectoryUserRow user={user} onProject={onProject} key={user.user_slug || "unattributed"} />)}
              </tbody>
            </table>
          </div>
        ) : <EmptyState icon={Users} title="No matching people" body="Clear the search or register Agents with a Commons user name." />)}
        {mode === "agents" && (agents.length ? (
          <div className="directory-table-wrap">
            <table className="directory-table">
              <thead>
                <tr><th scope="col">Agent</th><th scope="col">Controlled by</th><th scope="col">Project</th><th scope="col">Runtime</th><th scope="col">Last seen</th></tr>
              </thead>
              <tbody>
                {agents.map((agent) => <DirectoryAgentRow agent={agent} onAgent={onAgent} onProject={onProject} key={`${agent.project_id}:${agent.agent_id}`} />)}
              </tbody>
            </table>
          </div>
        ) : <EmptyState icon={Bot} title="No matching agents" body="Clear the search or register an Agent on this Relay." />)}
        {mode === "projects" && (projects.length ? (
          <div className="directory-table-wrap">
            <table className="directory-table">
              <thead>
                <tr><th scope="col">Project</th><th scope="col">People</th><th scope="col">Agents</th><th scope="col">Tasks</th><th scope="col">Last activity</th></tr>
              </thead>
              <tbody>
                {projects.map((project) => <DirectoryProjectRow project={project} onProject={onProject} key={project.project_id} />)}
              </tbody>
            </table>
          </div>
        ) : <EmptyState icon={Boxes} title="No matching projects" body="Clear the search to see every Relay project." />)}
      </section>
    </div>
  );
}

function ProjectOverviewView({
  detail,
  onAgent,
  onNavigate,
  onBroadcast,
}: {
  detail: ProjectOverviewDetail;
  onAgent: (agent: Agent) => void;
  onNavigate: (view: ConsoleView) => void;
  onBroadcast: (message: Message) => void;
}) {
  const activeTasks = detail.tasks.filter(isActiveTask);
  const activeAgents = detail.agents.filter((agent) => agent.presence !== "offline");
  return (
    <div className="view-stack">
      <div className="overview-grid">
        <button className="coordination-image" type="button" onClick={() => onNavigate("agents")}>
          <img src="/app/commons-architecture.png" alt="White interconnected walkways" />
          <span className="coordination-image__label">
            <Waypoints size={18} />
            <span className="coordination-image__agent-summary">
              <strong>{detail.project.active_agent_count} / {detail.project.agent_count}</strong>
              <span>active / registered agents</span>
            </span>
            <ArrowRight size={14} />
          </span>
        </button>
        <button className="coordination-signal" type="button" onClick={() => onNavigate("resources")}>
          <span className="coordination-signal__header"><span>Coordination signal</span><Radio size={17} /></span>
          <strong>{detail.project.blocked_task_count === 0 ? "Clear" : `${detail.project.blocked_task_count} blocked`}</strong>
          <span className="coordination-signal__copy">{detail.project.active_lease_count} active leases across {detail.project.active_task_count} current tasks.</span>
          <span className="signal-bars" aria-hidden="true">{[44, 68, 52, 88, 62, 76, 56, 92].map((height, index) => <span key={index} style={{ height: `${height}%` }} />)}</span>
          <ArrowRight className="coordination-signal__arrow" size={16} />
        </button>
      </div>

      <section className="content-section" aria-labelledby="project-broadcasts-title">
        <div className="section-heading">
          <div><h2 id="project-broadcasts-title">Project broadcasts</h2><p>Plans and status shared with every Agent in this Project.</p></div>
          <button className="section-action" type="button" onClick={() => onNavigate("broadcasts")}>View all <ArrowRight size={13} /></button>
        </div>
        {detail.broadcasts.length ? (
          <div className="broadcast-preview-grid">{detail.broadcasts.slice(0, 3).map((message) => <BroadcastPreview key={message.message_id} message={message} onClick={() => onBroadcast(message)} />)}</div>
        ) : <EmptyState icon={Inbox} title="No project broadcasts" body="Plans and project-wide status updates will appear here." />}
      </section>

      <section className="content-section" aria-labelledby="active-agents-title">
        <div className="section-heading">
          <div><h2 id="active-agents-title">Active agents</h2><p>Online and idle Agents with a recent Relay heartbeat.</p></div>
          <button className="section-action" type="button" onClick={() => onNavigate("agents")}>{detail.project.active_agent_count} active · {detail.project.agent_count} registered <ArrowRight size={13} /></button>
        </div>
        {activeAgents.length ? (
          <div className="agent-card-grid">{activeAgents.slice(0, 4).map((agent) => <AgentCard agent={agent} onClick={() => onAgent(agent)} key={agent.agent_id} />)}</div>
        ) : <EmptyState icon={Bot} title="No active agents" body="Registered Agents remain discoverable in the Agent directory while their presence is offline." />}
      </section>

      <section className="content-section" aria-labelledby="current-work-title">
        <div className="section-heading">
          <div><h2 id="current-work-title">Current work</h2><p>Explicit Agent reports, never inferred from message volume.</p></div>
          <button className="section-action" type="button" onClick={() => onNavigate("tasks")}>{detail.project.active_task_count} active <ArrowRight size={13} /></button>
        </div>
        {activeTasks.length ? <div className="task-rows">{activeTasks.slice(0, 5).map((task) => <TaskRow task={task} onClick={() => onNavigate("tasks")} key={task.task_id} />)}</div> : <EmptyState icon={Check} title="No active tasks" body="Completed and future tasks remain available in the Tasks view." />}
      </section>
    </div>
  );
}

function FilterTabs<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: Array<{ value: T; label: string }>; onChange: (value: T) => void }) {
  return (
    <div className="filter-tabs" role="group" aria-label={label}>
      {options.map((option) => <button type="button" className={value === option.value ? "filter-tab filter-tab--active" : "filter-tab"} onClick={() => onChange(option.value)} aria-pressed={value === option.value} key={option.value}>{option.label}</button>)}
    </div>
  );
}

function PageControls({ page, pageNumber, canPrevious, onPrevious, onNext }: { page: PageMeta; pageNumber: number; canPrevious: boolean; onPrevious: () => void; onNext: () => void }) {
  return (
    <nav className="page-controls" aria-label="Result pages">
      <button className="page-control" type="button" onClick={onPrevious} disabled={!canPrevious} title="Previous page" aria-label="Previous page"><ArrowLeft size={15} /></button>
      <span>Page {pageNumber} · {page.returned_count} shown</span>
      <button className="page-control" type="button" onClick={onNext} disabled={!page.has_more || !page.next_cursor} title="Next page" aria-label="Next page"><ArrowRight size={15} /></button>
    </nav>
  );
}

type PagedViewProps = {
  page: PageMeta;
  pageNumber: number;
  canPrevious: boolean;
  onPrevious: () => void;
  onNext: () => void;
};

function AgentsView({ agents, filter, onFilter, onAgent, ...paging }: { agents: Agent[]; filter: AgentFilter; onFilter: (filter: AgentFilter) => void; onAgent: (agent: Agent) => void } & PagedViewProps) {
  return (
    <div className="directory-view">
      <div className="view-toolbar"><FilterTabs label="Filter agents" value={filter} onChange={onFilter} options={[{ value: "active", label: "Active" }, { value: "all", label: "All" }, { value: "online", label: "Online" }, { value: "idle", label: "Idle" }, { value: "offline", label: "Offline" }]} /><span>{agents.length} on this page</span></div>
      {agents.length ? (
        <div className="directory-list">{agents.map((agent) => (
          <button className="directory-row" type="button" key={agent.agent_id} onClick={() => onAgent(agent)}>
            <AgentAvatar agent={agent} />
            <span className="directory-row__identity"><strong>{agentLabel(agent)}</strong><small>{agent.name || agent.agent_id}</small></span>
            <span className="directory-row__runtime"><strong>{agent.runtime}</strong><small>{agent.workspace || "Workspace hidden"}</small></span>
            <span className="directory-row__work"><strong>{agent.current_task?.title || agentWorkState(agent)}</strong><small>{agent.current_task?.current_step || "No declared task"}</small></span>
            <span className="directory-row__presence"><PresenceLabel presence={agent.presence} /><small>{formatRelative(agent.last_seen_at)}</small></span>
            <ArrowRight size={16} />
          </button>
        ))}</div>
      ) : <EmptyState icon={Users} title="No matching agents" body="Change the presence filter or search for another Agent." />}
      <PageControls {...paging} />
    </div>
  );
}

function TasksView({ tasks, filter, onFilter, ...paging }: { tasks: Task[]; filter: TaskFilter; onFilter: (filter: TaskFilter) => void } & PagedViewProps) {
  return (
    <div className="directory-view">
      <div className="view-toolbar"><FilterTabs label="Filter tasks" value={filter} onChange={onFilter} options={[{ value: "all", label: "All" }, { value: "active", label: "Active" }, { value: "blocked", label: "Blocked" }]} /><span>{tasks.length} on this page</span></div>
      {tasks.length ? <div className="task-rows task-rows--full">{tasks.map((task) => <TaskRow task={task} key={task.task_id} />)}</div> : <EmptyState icon={CircleDot} title="No matching tasks" body="Change the task filter or search for another task." />}
      <PageControls {...paging} />
    </div>
  );
}

function BroadcastsView({ broadcasts, onMessage, ...paging }: { broadcasts: Message[]; onMessage: (message: Message) => void } & PagedViewProps) {
  return (
    <div className="directory-view">
      {broadcasts.length ? <div className="message-list">{broadcasts.map((message) => (
      <button className="message-row" type="button" key={message.message_id} onClick={() => onMessage(message)}>
        <span className={`message-row__icon message-row__icon--${message.message_type}`}><Send size={17} /></span>
        <span className="message-row__body">
          <span className="message-row__heading"><strong>{message.sender_handle ? `@${message.sender_handle}` : message.sender_agent_id || "System"}</strong><span>to Project broadcast</span></span>
          <span className="message-row__copy">{message.body}</span>
          <span className="message-row__meta"><span>{sentenceCase(message.message_type)}</span><span>{message.acked_count}/{message.audience_count} acknowledged</span></span>
        </span>
        <time dateTime={message.created_at}>{formatClock(message.created_at)}</time>
        <ArrowRight size={15} />
      </button>
      ))}</div> : <EmptyState icon={Inbox} title="No matching broadcasts" body="Project-wide plans and status updates appear here. Direct messages stay in Agent details." />}
      <PageControls {...paging} />
    </div>
  );
}

function ResourcesView({ leases, filter, onFilter, ...paging }: { leases: Lease[]; filter: ResourceFilter; onFilter: (filter: ResourceFilter) => void } & PagedViewProps) {
  return (
    <div className="directory-view">
      <div className="view-toolbar"><FilterTabs label="Filter resources" value={filter} onChange={onFilter} options={[{ value: "active", label: "Active" }, { value: "all", label: "All" }]} /><span>{leases.length} on this page</span></div>
      {leases.length ? <div className="lease-list">{leases.map((lease) => (
      <article className="lease-row" key={lease.lease_id}>
        <div className={`lease-row__state lease-row__state--${lease.effective_state}`}><KeyRound size={17} /></div>
        <div className="lease-row__resource"><strong>{lease.canonical_resource_id}</strong><span>{lease.reason || "No reason supplied"}</span></div>
        <div><span className="table-label">Mode</span><strong>{sentenceCase(lease.mode)}</strong></div>
        <div><span className="table-label">Holder</span><strong>{lease.holder_handle ? `@${lease.holder_handle}` : lease.holder_agent_id || "Unknown"}</strong></div>
        <div><span className="table-label">Epoch</span><strong>{lease.fencing_epoch}</strong></div>
        <StatusBadge status={lease.effective_state} />
      </article>
      ))}</div> : <EmptyState icon={KeyRound} title="No matching resource leases" body="Lease activity appears when Agents coordinate shared operations." />}
      <PageControls {...paging} />
    </div>
  );
}

function calendarHeatLevel(total: number): number {
  if (total <= 0) return 0;
  if (total <= 2) return 1;
  if (total <= 5) return 2;
  if (total <= 11) return 3;
  return 4;
}

function calendarDayTitle(label: string, day: ActivityCalendarDay | undefined): string {
  if (!day || !day.total) return `${label}: no coordination activity`;
  const parts = [
    day.tasks && `${day.tasks} task ${day.tasks === 1 ? "event" : "events"}`,
    day.messages && `${day.messages} ${day.messages === 1 ? "message" : "messages"}`,
    day.leases && `${day.leases} lease ${day.leases === 1 ? "event" : "events"}`,
    day.agents && `${day.agents} agent ${day.agents === 1 ? "event" : "events"}`,
    day.other && `${day.other} other`,
  ].filter(Boolean);
  return `${label}: ${day.total} ${day.total === 1 ? "event" : "events"} — ${parts.join(", ")}`;
}

function RailHeader({
  live,
  calendar,
  selectedDay = null,
  onSelectDay,
}: {
  live: boolean;
  calendar?: ActivityCalendarDay[] | null;
  selectedDay?: string | null;
  onSelectDay?: (date: string) => void;
}) {
  const today = new Date();
  const byDate = new Map((calendar || []).map((day) => [day.date, day]));
  return (
    <>
      <div className="activity-rail__header">
        <div><strong>{new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(today)}</strong><span>{new Intl.DateTimeFormat("en", { weekday: "long" }).format(today)}</span></div>
        <span className={`live-state ${live ? "live-state--on" : ""}`}><Radio size={14} />{live ? "Live" : "Reconnecting"}</span>
      </div>
      <div className="activity-calendar" aria-label="Coordination activity over the last seven days" role="group">
        {Array.from({ length: 7 }, (_, index) => {
          const date = new Date(today);
          date.setDate(today.getDate() - 6 + index);
          const key = date.toISOString().slice(0, 10);
          const day = byDate.get(key);
          const label = new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(date);
          const classes = [index === 6 ? "selected" : "", selectedDay === key ? "viewing" : ""].filter(Boolean).join(" ");
          return (
            <button
              className={classes || undefined}
              type="button"
              key={key}
              title={calendarDayTitle(label, day)}
              aria-pressed={selectedDay === key}
              aria-label={`Show activity for ${label}`}
              onClick={onSelectDay ? () => onSelectDay(key) : undefined}
              disabled={!onSelectDay}
            >
              <small>{new Intl.DateTimeFormat("en", { weekday: "narrow" }).format(date)}</small>
              {date.getDate()}
              <i className={`calendar-heat calendar-heat--${calendarHeatLevel(day?.total || 0)}`} aria-hidden="true" />
            </button>
          );
        })}
      </div>
    </>
  );
}

const DAY_GROUPS: Array<{ key: string; label: string; icon: LucideIcon; match: (type: string) => boolean }> = [
  { key: "tasks", label: "Tasks", icon: CircleDot, match: (type) => type.startsWith("task") },
  { key: "messages", label: "Messages", icon: Send, match: (type) => type.startsWith("message") },
  { key: "leases", label: "Resources", icon: KeyRound, match: (type) => type.startsWith("lease") || type.startsWith("deploy") || type.startsWith("operation") },
  { key: "agents", label: "Agents", icon: Bot, match: (type) => type.startsWith("agent") },
  { key: "other", label: "Other", icon: Activity, match: () => true },
];

function DaySummaryRail({
  date,
  detail,
  loading,
  error,
  live,
  calendar,
  showProject,
  onSelectDay,
  onClose,
  onEvent,
}: {
  date: string;
  detail: DayActivity | null;
  loading: boolean;
  error: string;
  live: boolean;
  calendar?: ActivityCalendarDay[] | null;
  showProject: boolean;
  onSelectDay: (date: string) => void;
  onClose: () => void;
  onEvent: (event: DayActivityEvent) => void;
}) {
  const label = new Intl.DateTimeFormat("en", { weekday: "long", month: "short", day: "numeric" }).format(new Date(`${date}T12:00:00Z`));
  const groups = DAY_GROUPS.map((group) => ({ ...group, events: [] as DayActivityEvent[] }));
  (detail?.events || []).forEach((event) => {
    const group = groups.find((candidate) => candidate.match(event.event_type));
    if (group) group.events.push(event);
  });
  const populated = groups.filter((group) => group.events.length);
  return (
    <aside className="activity-rail" aria-label={`Coordination activity on ${label}`}>
      <RailHeader live={live} calendar={calendar} selectedDay={date} onSelectDay={onSelectDay} />
      <div className="timeline-heading"><span>{label}</span><button className="day-summary__close" type="button" onClick={onClose}>Back to live <X size={12} /></button></div>
      {loading && !detail ? (
        <div className="rail-skeleton" aria-hidden="true"><span /><span /><span /><span /></div>
      ) : error && !detail ? (
        <EmptyState icon={AlertTriangle} title="Day unavailable" body={error} />
      ) : !detail || !detail.totals.total ? (
        <EmptyState icon={Activity} title="A quiet day" body={`No coordination events were recorded on ${label}.`} />
      ) : (
        <div className="day-summary">
          {populated.map((group) => {
            const GroupIcon = group.icon;
            return (
              <section className="day-summary__group" key={group.key} aria-label={`${group.label} events`}>
                <div className="day-summary__group-heading"><GroupIcon size={14} /><span>{group.label}</span><small>{group.events.length}</small></div>
                {group.events.map((event) => (
                  <button className={`day-summary__event day-summary__event--${eventTone(event.event_type)}`} type="button" key={event.event_id} onClick={() => onEvent(event)}>
                    <span className="day-summary__body">
                      <strong>{event.actor_handle ? `@${event.actor_handle}` : event.actor_agent_id || "Relay"}</strong>
                      <span>{eventSummary(event)}</span>
                      <small>{showProject && event.project_display_name ? `${event.project_display_name} · ` : ""}{formatClock(event.created_at)}</small>
                    </span>
                    <ChevronRight size={13} />
                  </button>
                ))}
              </section>
            );
          })}
        </div>
      )}
    </aside>
  );
}

function ActivityRail({ events, live, calendar, selectedDay, onSelectDay, onEvent }: { events: ActivityEvent[]; live: boolean; calendar?: ActivityCalendarDay[] | null; selectedDay?: string | null; onSelectDay?: (date: string) => void; onEvent: (event: ActivityEvent) => void }) {
  return (
    <aside className="activity-rail" aria-label="Project activity timeline">
      <RailHeader live={live} calendar={calendar} selectedDay={selectedDay} onSelectDay={onSelectDay} />
      <div className="timeline-heading"><span>Project activity</span><small>{events.length} recent events</small></div>
      <div className="timeline">
        {events.length ? events.slice(0, 30).map((event) => {
          const Icon = eventIcon(event.event_type);
          return (
            <article className="timeline-event" key={event.event_id}>
              <time dateTime={event.created_at}>{formatClock(event.created_at)}</time>
              <div className="timeline-event__line"><span /></div>
              <button className={`timeline-event__card timeline-event__card--${eventTone(event.event_type)}`} type="button" onClick={() => onEvent(event)}>
                <Icon size={15} />
                <span><strong>{event.actor_handle ? `@${event.actor_handle}` : event.actor_agent_id || "Relay"}</strong><small>{eventSummary(event)}</small></span>
                <ChevronRight size={13} />
              </button>
            </article>
          );
        }) : <EmptyState icon={Activity} title="No activity yet" body="Relay events will stream into this timeline." />}
      </div>
    </aside>
  );
}

function WorkspaceBroadcastRail({ broadcasts, live, calendar, selectedDay, onSelectDay, onBroadcast }: { broadcasts: WorkspaceBroadcast[]; live: boolean; calendar?: ActivityCalendarDay[] | null; selectedDay?: string | null; onSelectDay?: (date: string) => void; onBroadcast: (message: WorkspaceBroadcast) => void }) {
  return (
    <aside className="activity-rail" aria-label="Workspace broadcasts">
      <RailHeader live={live} calendar={calendar} selectedDay={selectedDay} onSelectDay={onSelectDay} />
      <div className="timeline-heading"><span>Workspace broadcasts</span><small>{broadcasts.length} recent</small></div>
      <div className="workspace-broadcast-list">
        {broadcasts.length ? broadcasts.map((message) => (
          <button className="workspace-broadcast-card" type="button" key={message.message_id} onClick={() => onBroadcast(message)}>
            <span className="workspace-broadcast-card__top"><span>{message.project_display_name}</span><time dateTime={message.created_at}>{formatClock(message.created_at)}</time></span>
            <strong>{message.sender_handle ? `@${message.sender_handle}` : message.sender_agent_id || "Relay"}</strong>
            <span>{message.body}</span>
            <small>{message.acked_count}/{message.audience_count} acknowledged <ArrowRight size={12} /></small>
          </button>
        )) : <EmptyState icon={Inbox} title="No broadcasts yet" body="Project-wide messages will appear here." />}
      </div>
    </aside>
  );
}

function ProjectActivityPlaceholder({ live, loading }: { live: boolean; loading: boolean }) {
  return (
    <aside className="activity-rail" aria-label={loading ? "Loading project activity" : "Project activity unavailable"}>
      <RailHeader live={live} />
      <div className="timeline-heading"><span>Project activity</span><small>{loading ? "Loading" : "Unavailable"}</small></div>
      {loading ? (
        <div className="rail-skeleton" aria-hidden="true"><span /><span /><span /><span /></div>
      ) : (
        <EmptyState icon={Activity} title="Project activity unavailable" body="Retry the Project request to load its activity timeline." />
      )}
    </aside>
  );
}

function AgentDrawer({ agent, detail, loading, onClose, onMessage, onLoadMore }: { agent: Agent; detail: AgentDetail | null; loading: boolean; onClose: () => void; onMessage: (message: Message) => void; onLoadMore: () => void }) {
  const displayAgent = detail?.agent || agent;
  const messages = detail?.direct_messages.items || [];
  const leases = detail?.leases || [];
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="agent-drawer" role="dialog" aria-modal="true" aria-labelledby="agent-drawer-title">
        <button className="icon-button agent-drawer__close" type="button" onClick={onClose} title="Close agent details" aria-label="Close agent details"><X size={18} /></button>
        <div className="agent-drawer__identity">
          <AgentAvatar agent={displayAgent} size="large" />
          <div><PresenceLabel presence={displayAgent.presence} /><h2 id="agent-drawer-title">{agentLabel(displayAgent)}</h2><p>{displayAgent.runtime} · {displayAgent.contact_code || "No contact code"}</p></div>
        </div>
        <div className="agent-drawer__stats">
          <div><strong>{displayAgent.active_lease_count}</strong><span>Active leases</span></div>
          <div><strong>{messages.length}</strong><span>Direct messages</span></div>
          <div><strong>{formatRelative(displayAgent.last_seen_at)}</strong><span>Last heartbeat</span></div>
        </div>
        <section className="drawer-section">
          <div className="drawer-section__heading"><h3>Current work</h3><span>{agentWorkState(displayAgent)}</span></div>
          {displayAgent.current_task ? (
            <div className="drawer-task">
              <div><strong>{displayAgent.current_task.title}</strong><StatusBadge status={displayAgent.current_task.status} /></div>
              <p>{displayAgent.current_task.current_step || displayAgent.current_task.summary}</p>
              <TaskProgress task={displayAgent.current_task} />
              {displayAgent.current_task.next_step && <span className="next-step"><ArrowRight size={14} /> Next: {displayAgent.current_task.next_step}</span>}
            </div>
          ) : <p className="drawer-muted">No active task reported.</p>}
        </section>
        <section className="drawer-section"><h3>Active resources</h3>{leases.length ? leases.map((lease) => <div className="drawer-resource" key={lease.lease_id}><KeyRound size={15} /><span>{lease.canonical_resource_id}</span><small>e{lease.fencing_epoch}</small></div>) : <p className="drawer-muted">No active resource leases.</p>}</section>
        <section className="drawer-section"><h3>Direct messages</h3>{loading && !detail ? <div className="drawer-loading" aria-label="Loading agent details"><span /><span /><span /></div> : messages.length ? messages.map((message) => {
          const sent = message.sender_agent_id === displayAgent.agent_id;
          const peer = sent ? message.recipient_handle || message.recipient_agent_id : message.sender_handle || message.sender_agent_id;
          return <button className="drawer-message" type="button" key={message.message_id} onClick={() => onMessage(message)}><span>{sent ? "To" : "From"} {peer ? `@${String(peer).replace(/^@/, "")}` : "Agent"}</span><p>{message.body}</p><time dateTime={message.created_at}>{formatClock(message.created_at)}</time><ArrowRight size={13} /></button>;
        }) : <p className="drawer-muted">No direct messages with this Agent.</p>}{detail?.direct_messages.page.has_more && <button className="drawer-load-more" type="button" onClick={onLoadMore} disabled={loading}>Load more <ArrowRight size={13} /></button>}</section>
      </section>
    </div>
  );
}

function MessageDrawer({ message, projectName, onClose }: { message: Message | WorkspaceBroadcast; projectName: string; onClose: () => void }) {
  const direct = Boolean(message.recipient_agent_id);
  return (
    <div className="drawer-backdrop drawer-backdrop--message" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="message-drawer" role="dialog" aria-modal="true" aria-labelledby="message-drawer-title">
        <button className="icon-button agent-drawer__close" type="button" onClick={onClose} title="Close message details" aria-label="Close message details"><X size={18} /></button>
        <div className="message-drawer__heading"><span className={`message-row__icon message-row__icon--${message.message_type}`}>{direct ? <MessageSquareText size={18} /> : <Send size={18} />}</span><div><span>{direct ? "Direct message" : "Project broadcast"}</span><h2 id="message-drawer-title">{sentenceCase(message.message_type)}</h2></div></div>
        <dl className="message-metadata">
          <div><dt>Project</dt><dd>{projectName}</dd></div>
          <div><dt>From</dt><dd>{message.sender_handle ? `@${message.sender_handle}` : message.sender_agent_id || "Relay"}</dd></div>
          <div><dt>To</dt><dd>{direct ? message.recipient_handle ? `@${message.recipient_handle}` : message.recipient_agent_id : "All Project Agents"}</dd></div>
          <div><dt>Sent</dt><dd>{formatDate(message.created_at)} · {formatClock(message.created_at)}</dd></div>
        </dl>
        <div className="message-drawer__body">{message.body}</div>
        <div className="message-drawer__receipt"><span>{message.acked_count} acknowledged</span><span>{message.audience_count} recipients</span></div>
        <p className="message-drawer__id">{message.message_id}</p>
      </section>
    </div>
  );
}

function ProjectStrip({ projects, projectId, onWorkspace, onProject }: { projects: ProjectSummary[]; projectId: string; onWorkspace: () => void; onProject: (projectId: string) => void }) {
  return (
    <nav className="project-strip" aria-label="Switch project">
      <button type="button" className={!projectId ? "project-strip__item project-strip__item--active" : "project-strip__item"} onClick={onWorkspace}><Boxes size={15} />All projects</button>
      {projects.map((project) => <button type="button" className={projectId === project.project_id ? "project-strip__item project-strip__item--active" : "project-strip__item"} onClick={() => onProject(project.project_id)} key={project.project_id}><span className={project.active_agent_count ? "project-strip__signal project-strip__signal--active" : "project-strip__signal"} />{project.display_name}</button>)}
    </nav>
  );
}

function ProjectTabs({ view, onView }: { view: ConsoleView; onView: (view: ConsoleView) => void }) {
  return (
    <nav className="project-tabs" aria-label="Project views">
      {PROJECT_NAV_ITEMS.map(({ id, label, icon: Icon }) => <button type="button" className={view === id ? "project-tab project-tab--active" : "project-tab"} onClick={() => onView(id)} aria-current={view === id ? "page" : undefined} key={id}><Icon size={15} />{label}</button>)}
    </nav>
  );
}

function Dashboard({ onUnauthorized }: { onUnauthorized: () => void }) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [village, setVillage] = useState<VillageSnapshot | null>(null);
  const [villageLoading, setVillageLoading] = useState(true);
  const [villageError, setVillageError] = useState("");
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("overview");
  const [directory, setDirectory] = useState<DirectorySnapshot | null>(null);
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [directoryError, setDirectoryError] = useState("");
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [dayDetail, setDayDetail] = useState<DayActivity | null>(null);
  const [dayLoading, setDayLoading] = useState(false);
  const [dayError, setDayError] = useState("");
  const [projectId, setProjectId] = useState("");
  const [detail, setDetail] = useState<ProjectOverviewDetail | null>(null);
  const [view, setView] = useState<ConsoleView>("overview");
  const [workspaceFilter, setWorkspaceFilter] = useState<WorkspaceFilter>("all");
  const [agentFilter, setAgentFilter] = useState<AgentFilter>("active");
  const [taskFilter, setTaskFilter] = useState<TaskFilter>("all");
  const [resourceFilter, setResourceFilter] = useState<ResourceFilter>("active");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [error, setError] = useState("");
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [projectLoadingId, setProjectLoadingId] = useState<string | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [live, setLive] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [selectedAgentDetail, setSelectedAgentDetail] = useState<AgentDetail | null>(null);
  const [agentDetailLoading, setAgentDetailLoading] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState<Message | WorkspaceBroadcast | null>(null);
  const [agentsPage, setAgentsPage] = useState<AgentsPage | null>(null);
  const [tasksPage, setTasksPage] = useState<TasksPage | null>(null);
  const [broadcastsPage, setBroadcastsPage] = useState<MessagesPage | null>(null);
  const [leasesPage, setLeasesPage] = useState<LeasesPage | null>(null);
  const [loadedViewRequestKey, setLoadedViewRequestKey] = useState("");
  const [viewRefreshVersion, setViewRefreshVersion] = useState(0);
  const [agentRefreshVersion, setAgentRefreshVersion] = useState(0);
  const [pagination, setPagination] = useState<{ key: string; cursor: string | null; history: Array<string | null> }>({ key: "", cursor: null, history: [] });
  const refreshTimer = useRef<number | null>(null);
  const projectRequestId = useRef(0);
  const viewRequestId = useRef(0);
  const agentRequestId = useRef(0);
  const selectedProjectId = useRef("");
  const workspaceViewRef = useRef<WorkspaceView>("overview");
  const selectedAgentRef = useRef<Agent | null>(null);
  const dayRequestId = useRef(0);
  const selectedDayRef = useRef<string | null>(null);
  const currentViewRequestKey = useRef("");
  const projectCache = useRef(new Map<string, ProjectOverviewDetail>());

  const handleError = useCallback((caught: unknown) => {
    if (caught instanceof ApiError && caught.status === 401) {
      onUnauthorized();
      return;
    }
    setError(caught instanceof Error ? caught.message : "Unable to load Console data.");
  }, [onUnauthorized]);

  const refreshOverview = useCallback(async () => {
    try {
      const next = await getOverview();
      setOverview(next);
      setError("");
    } catch (caught) {
      handleError(caught);
    } finally {
      setOverviewLoading(false);
    }
  }, [handleError]);

  const refreshVillage = useCallback(async () => {
    try {
      const next = await getVillage();
      setVillage(next);
      setVillageError("");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        onUnauthorized();
        return;
      }
      setVillageError(caught instanceof Error ? caught.message : "Unable to load the Agent village.");
    } finally {
      setVillageLoading(false);
    }
  }, [onUnauthorized]);

  const refreshDirectory = useCallback(async () => {
    try {
      const next = await getDirectory();
      setDirectory(next);
      setDirectoryError("");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        onUnauthorized();
        return;
      }
      setDirectoryError(caught instanceof Error ? caught.message : "Unable to load the workspace directory.");
    } finally {
      setDirectoryLoading(false);
    }
  }, [onUnauthorized]);

  const openDay = useCallback(async (date: string) => {
    const requestId = ++dayRequestId.current;
    selectedDayRef.current = date;
    setSelectedDay(date);
    setDayDetail(null);
    setDayError("");
    setDayLoading(true);
    try {
      const next = await getDayActivity(date, selectedProjectId.current || undefined);
      if (requestId !== dayRequestId.current) return;
      setDayDetail(next);
    } catch (caught) {
      if (requestId !== dayRequestId.current) return;
      if (caught instanceof ApiError && caught.status === 401) {
        onUnauthorized();
        return;
      }
      setDayError(caught instanceof Error ? caught.message : "Unable to load activity for this day.");
    } finally {
      if (requestId === dayRequestId.current) setDayLoading(false);
    }
  }, [onUnauthorized]);

  const refreshProject = useCallback(async (id: string, showLoading = false) => {
    const requestId = ++projectRequestId.current;
    if (!id) {
      setDetail(null);
      setProjectLoadingId(null);
      return;
    }
    if (showLoading) setProjectLoadingId(id);
    try {
      const next = await getProjectOverview(id);
      if (requestId !== projectRequestId.current || selectedProjectId.current !== id) return;
      if (next.project.project_id !== id) throw new Error(`Relay returned Project ${next.project.project_id} for ${id}.`);
      projectCache.current.set(id, next);
      setDetail(next);
      setError("");
    } catch (caught) {
      if (requestId !== projectRequestId.current || selectedProjectId.current !== id) return;
      handleError(caught);
    } finally {
      if (requestId === projectRequestId.current && selectedProjectId.current === id) {
        setProjectLoadingId((current) => current === id ? null : current);
      }
    }
  }, [handleError]);

  useEffect(() => { void refreshOverview(); void refreshVillage(); }, [refreshOverview, refreshVillage]);
  useEffect(() => { if (projectId) void refreshProject(projectId, !projectCache.current.has(projectId)); }, [projectId, refreshProject]);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  const collectionFilter = view === "agents" ? agentFilter : view === "tasks" ? taskFilter : view === "resources" ? resourceFilter : "all";
  const collectionKey = `${projectId}:${view}:${collectionFilter}:${debouncedQuery.toLowerCase()}`;
  const pageCursor = pagination.key === collectionKey ? pagination.cursor : null;
  const pageHistory = pagination.key === collectionKey ? pagination.history : [];
  const viewRequestKey = `${collectionKey}:${pageCursor || "first"}`;
  currentViewRequestKey.current = viewRequestKey;

  useEffect(() => {
    if (!projectId || view === "overview" || detail?.project.project_id !== projectId) return;
    const requestId = ++viewRequestId.current;
    const expectedKey = viewRequestKey;
    setViewLoading(true);
    setPagination((current) => current.key === collectionKey ? current : { key: collectionKey, cursor: null, history: [] });
    if (view === "agents") setAgentsPage(null);
    if (view === "tasks") setTasksPage(null);
    if (view === "broadcasts") setBroadcastsPage(null);
    if (view === "resources") setLeasesPage(null);

    async function loadView() {
      try {
        if (view === "agents") {
          const next = await getProjectAgents(projectId, { limit: 50, cursor: pageCursor, filter: agentFilter, query: debouncedQuery });
          if (requestId === viewRequestId.current && selectedProjectId.current === projectId && currentViewRequestKey.current === expectedKey) setAgentsPage(next);
        } else if (view === "tasks") {
          const next = await getProjectTasks(projectId, { limit: 50, cursor: pageCursor, filter: taskFilter, query: debouncedQuery });
          if (requestId === viewRequestId.current && selectedProjectId.current === projectId && currentViewRequestKey.current === expectedKey) setTasksPage(next);
        } else if (view === "broadcasts") {
          const next = await getProjectBroadcasts(projectId, { limit: 50, cursor: pageCursor, query: debouncedQuery });
          if (requestId === viewRequestId.current && selectedProjectId.current === projectId && currentViewRequestKey.current === expectedKey) setBroadcastsPage(next);
        } else if (view === "resources") {
          const next = await getProjectLeases(projectId, { limit: 50, cursor: pageCursor, filter: resourceFilter, query: debouncedQuery });
          if (requestId === viewRequestId.current && selectedProjectId.current === projectId && currentViewRequestKey.current === expectedKey) setLeasesPage(next);
        }
        if (requestId === viewRequestId.current && selectedProjectId.current === projectId && currentViewRequestKey.current === expectedKey) setError("");
      } catch (caught) {
        if (requestId === viewRequestId.current && selectedProjectId.current === projectId && currentViewRequestKey.current === expectedKey) handleError(caught);
      } finally {
        if (requestId === viewRequestId.current && selectedProjectId.current === projectId && currentViewRequestKey.current === expectedKey) {
          setLoadedViewRequestKey(expectedKey);
          setViewLoading(false);
        }
      }
    }
    void loadView();
  }, [agentFilter, collectionKey, debouncedQuery, detail?.project.project_id, handleError, pageCursor, projectId, resourceFilter, taskFilter, view, viewRefreshVersion, viewRequestKey]);

  const loadAgentDetail = useCallback(async (agent: Agent, cursor: string | null = null, append = false) => {
    const id = selectedProjectId.current;
    const requestId = ++agentRequestId.current;
    setAgentDetailLoading(true);
    try {
      const next = await getAgentDetail(id, agent.agent_id, { limit: 20, cursor });
      if (requestId !== agentRequestId.current || selectedProjectId.current !== id || selectedAgentRef.current?.agent_id !== agent.agent_id) return;
      setSelectedAgent(next.agent);
      selectedAgentRef.current = next.agent;
      setSelectedAgentDetail((current) => append && current ? {
        ...next,
        direct_messages: {
          items: [...current.direct_messages.items, ...next.direct_messages.items],
          page: next.direct_messages.page,
        },
      } : next);
    } catch (caught) {
      if (requestId === agentRequestId.current) handleError(caught);
    } finally {
      if (requestId === agentRequestId.current) setAgentDetailLoading(false);
    }
  }, [handleError]);

  useEffect(() => {
    if (agentRefreshVersion > 0 && selectedAgentRef.current) void loadAgentDetail(selectedAgentRef.current);
  }, [agentRefreshVersion, loadAgentDetail]);

  const streamReady = overview !== null;
  useEffect(() => {
    if (!streamReady || !overview) return;
    const params = new URLSearchParams({ after: String(overview.latest_event_id) });
    if (projectId) params.set("project_id", projectId);
    const stream = new EventSource(`/v1/console/events?${params.toString()}`);
    stream.addEventListener("open", () => setLive(true));
    stream.addEventListener("error", () => setLive(false));
    stream.addEventListener("activity", (rawEvent) => {
      setLive(true);
      try {
        const event = JSON.parse((rawEvent as MessageEvent<string>).data) as ActivityEvent;
        const recipient = String(event.payload.recipient_agent_id || "");
        if (selectedAgentRef.current && [event.actor_agent_id, recipient].includes(selectedAgentRef.current.agent_id)) {
          setAgentRefreshVersion((current) => current + 1);
        }
      } catch {
        // A malformed event still triggers a conservative summary refresh.
      }
      if (refreshTimer.current != null) window.clearTimeout(refreshTimer.current);
      refreshTimer.current = window.setTimeout(() => {
        void refreshOverview();
        void refreshVillage();
        if (workspaceViewRef.current === "directory" && !selectedProjectId.current) void refreshDirectory();
        if (projectId) void refreshProject(projectId);
        if (projectId && view !== "overview") setViewRefreshVersion((current) => current + 1);
      }, 250);
    });
    return () => {
      stream.close();
      if (refreshTimer.current != null) window.clearTimeout(refreshTimer.current);
    };
  }, [projectId, refreshDirectory, refreshOverview, refreshProject, refreshVillage, streamReady, view]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      void refreshOverview();
      void refreshVillage();
      if (workspaceViewRef.current === "directory" && !selectedProjectId.current) void refreshDirectory();
      if (projectId) void refreshProject(projectId);
      if (projectId && view !== "overview") setViewRefreshVersion((current) => current + 1);
      if (selectedAgentRef.current) setAgentRefreshVersion((current) => current + 1);
    }, 20000);
    return () => window.clearInterval(interval);
  }, [projectId, refreshDirectory, refreshOverview, refreshProject, refreshVillage, view]);

  const activeDetail = detail?.project.project_id === projectId ? detail : null;
  const projectIsLoading = Boolean(projectId && projectLoadingId === projectId && !activeDetail);
  const selectedProject = overview?.projects.find((project) => project.project_id === projectId) || null;
  const currentTitle = PROJECT_NAV_ITEMS.find((item) => item.id === view)?.label || "Overview";
  const normalizedQuery = query.trim().toLowerCase();

  function closeDay() {
    dayRequestId.current += 1;
    selectedDayRef.current = null;
    setSelectedDay(null);
    setDayDetail(null);
    setDayError("");
    setDayLoading(false);
  }

  function toggleDay(date: string) {
    if (selectedDayRef.current === date) closeDay();
    else void openDay(date);
  }

  function openWorkspace(filter: WorkspaceFilter = "all") {
    selectedProjectId.current = "";
    projectRequestId.current += 1;
    viewRequestId.current += 1;
    setProjectId("");
    setDetail(null);
    setProjectLoadingId(null);
    setView("overview");
    workspaceViewRef.current = "overview";
    setWorkspaceView("overview");
    setWorkspaceFilter(filter);
    setQuery("");
    closeAgent();
    closeDay();
    setSelectedMessage(null);
  }

  function openDirectory() {
    selectedProjectId.current = "";
    projectRequestId.current += 1;
    viewRequestId.current += 1;
    setProjectId("");
    setDetail(null);
    setProjectLoadingId(null);
    setView("overview");
    workspaceViewRef.current = "directory";
    setWorkspaceView("directory");
    setWorkspaceFilter("all");
    setQuery("");
    closeAgent();
    closeDay();
    setSelectedMessage(null);
    if (!directory) setDirectoryLoading(true);
    void refreshDirectory();
  }

  function openProject(id: string, nextView: ConsoleView = "overview") {
    selectedProjectId.current = id;
    workspaceViewRef.current = "overview";
    setWorkspaceView("overview");
    projectRequestId.current += 1;
    viewRequestId.current += 1;
    setProjectId(id);
    const cached = projectCache.current.get(id) || null;
    setDetail(cached);
    setProjectLoadingId(cached ? null : id);
    setView(nextView);
    setError("");
    setQuery("");
    closeAgent();
    closeDay();
    setSelectedMessage(null);
  }

  function openProjectView(nextView: ConsoleView) {
    viewRequestId.current += 1;
    setView(nextView);
    setQuery("");
  }

  function openAgents(filter: AgentFilter) {
    viewRequestId.current += 1;
    setAgentFilter(filter);
    openProjectView("agents");
  }

  function openTasks(filter: TaskFilter) {
    viewRequestId.current += 1;
    setTaskFilter(filter);
    openProjectView("tasks");
  }

  function changeAgentFilter(filter: AgentFilter) {
    viewRequestId.current += 1;
    setAgentFilter(filter);
  }

  function changeTaskFilter(filter: TaskFilter) {
    viewRequestId.current += 1;
    setTaskFilter(filter);
  }

  function changeResourceFilter(filter: ResourceFilter) {
    viewRequestId.current += 1;
    setResourceFilter(filter);
  }

  function openWorkspaceBroadcast(message: WorkspaceBroadcast) {
    selectedProjectId.current = message.project_id;
    workspaceViewRef.current = "overview";
    setWorkspaceView("overview");
    projectRequestId.current += 1;
    viewRequestId.current += 1;
    setProjectId(message.project_id);
    const cached = projectCache.current.get(message.project_id) || null;
    setDetail(cached);
    setProjectLoadingId(cached ? null : message.project_id);
    setView("broadcasts");
    setQuery("");
    closeDay();
    setSelectedMessage(message);
  }

  function openVillageAgent(id: string, agent: Agent) {
    openProject(id);
    openAgent(agent);
  }

  function handleActivity(event: ActivityEvent) {
    if (!activeDetail) return;
    if (event.event_type.startsWith("message")) {
      const messageId = String(event.payload.message_id || "");
      const message = [...activeDetail.broadcasts, ...(broadcastsPage?.broadcasts || [])].find((item) => item.message_id === messageId);
      const recipient = String(event.payload.recipient_agent_id || "");
      if (recipient) {
        const agent = [...activeDetail.agents, ...(agentsPage?.agents || [])].find((item) => item.agent_id === recipient || item.agent_id === event.actor_agent_id);
        openAgents("all");
        openAgentById(agent?.agent_id || event.actor_agent_id || recipient);
        return;
      }
      openProjectView("broadcasts");
      if (message) setSelectedMessage(message);
      return;
    }
    if (event.event_type.startsWith("agent")) {
      openAgents("all");
      const agent = [...activeDetail.agents, ...(agentsPage?.agents || [])].find((item) => item.agent_id === event.actor_agent_id);
      if (agent) openAgent(agent);
      else if (event.actor_agent_id) openAgentById(event.actor_agent_id);
      return;
    }
    if (event.event_type.startsWith("task")) {
      openTasks("all");
      return;
    }
    if (event.event_type.startsWith("lease") || event.event_type.startsWith("deploy")) {
      openProjectView("resources");
      return;
    }
    openProjectView("overview");
  }

  async function signOut() {
    try { await logout(); } finally { onUnauthorized(); }
  }

  function openAgent(agent: Agent) {
    selectedAgentRef.current = agent;
    setSelectedAgent(agent);
    setSelectedAgentDetail(null);
    void loadAgentDetail(agent);
  }

  async function openAgentById(agentId: string) {
    if (!agentId) return;
    const known = [...(activeDetail?.agents || []), ...(agentsPage?.agents || [])].find((agent) => agent.agent_id === agentId);
    if (known) {
      openAgent(known);
      return;
    }
    const id = selectedProjectId.current;
    const requestId = ++agentRequestId.current;
    setAgentDetailLoading(true);
    try {
      const next = await getAgentDetail(id, agentId, { limit: 20 });
      if (requestId !== agentRequestId.current || selectedProjectId.current !== id) return;
      selectedAgentRef.current = next.agent;
      setSelectedAgent(next.agent);
      setSelectedAgentDetail(next);
    } catch (caught) {
      if (requestId === agentRequestId.current) handleError(caught);
    } finally {
      if (requestId === agentRequestId.current) setAgentDetailLoading(false);
    }
  }

  function closeAgent() {
    agentRequestId.current += 1;
    selectedAgentRef.current = null;
    setSelectedAgent(null);
    setSelectedAgentDetail(null);
    setAgentDetailLoading(false);
  }

  function loadMoreAgentMessages() {
    const cursor = selectedAgentDetail?.direct_messages.page.next_cursor;
    if (selectedAgentRef.current && cursor) void loadAgentDetail(selectedAgentRef.current, cursor, true);
  }

  const currentPage = view === "agents" ? agentsPage?.page : view === "tasks" ? tasksPage?.page : view === "broadcasts" ? broadcastsPage?.page : view === "resources" ? leasesPage?.page : null;

  function nextPage() {
    if (!currentPage?.next_cursor) return;
    viewRequestId.current += 1;
    setPagination({ key: collectionKey, cursor: currentPage.next_cursor, history: [...pageHistory, pageCursor] });
  }

  function previousPage() {
    if (!pageHistory.length) return;
    viewRequestId.current += 1;
    const history = pageHistory.slice(0, -1);
    setPagination({ key: collectionKey, cursor: pageHistory[pageHistory.length - 1], history });
  }

  const pagingProps = currentPage ? {
    page: currentPage,
    pageNumber: pageHistory.length + 1,
    canPrevious: pageHistory.length > 0,
    onPrevious: previousPage,
    onNext: nextPage,
  } : null;

  let projectContent: ReactNode = null;
  if (activeDetail) {
    if (view === "overview") projectContent = <ProjectOverviewView detail={activeDetail} onAgent={openAgent} onNavigate={openProjectView} onBroadcast={setSelectedMessage} />;
    else if (viewLoading || loadedViewRequestKey !== viewRequestKey) projectContent = <div className="content-skeleton content-skeleton--compact" aria-label={`Loading ${view}`} aria-busy="true"><span /><span /><span /></div>;
    else if (view === "agents" && agentsPage && pagingProps) projectContent = <AgentsView agents={agentsPage.agents} filter={agentFilter} onFilter={changeAgentFilter} onAgent={openAgent} {...pagingProps} />;
    else if (view === "tasks" && tasksPage && pagingProps) projectContent = <TasksView tasks={tasksPage.tasks} filter={taskFilter} onFilter={changeTaskFilter} {...pagingProps} />;
    else if (view === "broadcasts" && broadcastsPage && pagingProps) projectContent = <BroadcastsView broadcasts={broadcastsPage.broadcasts} onMessage={setSelectedMessage} {...pagingProps} />;
    else if (view === "resources" && leasesPage && pagingProps) projectContent = <ResourcesView leases={leasesPage.leases} filter={resourceFilter} onFilter={changeResourceFilter} {...pagingProps} />;
  }

  const projectNameForMessage = selectedMessage && "project_display_name" in selectedMessage
    ? selectedMessage.project_display_name
    : selectedProject?.display_name || activeDetail?.project.display_name || "Project";

  return (
    <main className="console-page">
      <section className="console-shell">
        <nav className="side-nav" aria-label="Console navigation">
          <BrandMark compact />
          <div className="side-nav__items">
            <button className={`nav-button ${!projectId && workspaceView === "overview" && workspaceFilter === "all" ? "nav-button--active" : ""}`} type="button" onClick={() => openWorkspace("all")} title="Workspace overview" aria-label="Workspace overview"><LayoutDashboard size={19} /></button>
            <button className={`nav-button ${!projectId && workspaceView === "overview" && workspaceFilter !== "all" ? "nav-button--active" : ""}`} type="button" onClick={() => { openWorkspace("all"); scrollToProjects(); }} title="Projects" aria-label="Projects"><Boxes size={19} /></button>
            <button className={`nav-button ${!projectId && workspaceView === "directory" ? "nav-button--active" : ""}`} type="button" onClick={openDirectory} title="Directory" aria-label="Directory"><Users size={19} /></button>
          </div>
          <button className="nav-button nav-button--logout" type="button" onClick={signOut} title="Sign out" aria-label="Sign out"><LogOut size={18} /></button>
        </nav>

        <div className="workspace-pane">
          <header className="workspace-topbar">
            <ProjectStrip projects={overview?.projects || []} projectId={projectId} onWorkspace={() => openWorkspace("all")} onProject={openProject} />
            <div className="search-field">
              <Search size={16} aria-hidden="true" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={projectId ? `Search ${currentTitle.toLowerCase()}` : workspaceView === "directory" ? "Search directory" : "Search projects"} aria-label={projectId ? `Search ${currentTitle.toLowerCase()}` : workspaceView === "directory" ? "Search directory" : "Search projects"} />
            </div>
            <button className="icon-button" type="button" onClick={() => { void refreshOverview(); void refreshVillage(); if (projectId) void refreshProject(projectId, !activeDetail); if (projectId && view !== "overview") setViewRefreshVersion((current) => current + 1); }} title="Refresh data" aria-label="Refresh data"><RefreshCw size={17} /></button>
          </header>

          <div className="workspace-content">
            {projectId && (
              <header className="page-heading">
                <div>
                  {view !== "overview" && <p>{selectedProject?.display_name || activeDetail?.project.display_name || "Project"}</p>}
                  <h1>{view === "overview" ? selectedProject?.display_name || activeDetail?.project.display_name || "Project" : currentTitle}</h1>
                </div>
              </header>
            )}

            {projectId && <ProjectTabs view={view} onView={openProjectView} />}

            {projectId && activeDetail && (
              <div className="metrics-row metrics-row--project" aria-label="Project summary">
                <MetricButton icon={Gauge} label="Active tasks" value={activeDetail.project.active_task_count} detail="Current work" tone="yellow" onClick={() => openTasks("active")} />
                <MetricButton icon={AlertTriangle} label="Blocked" value={activeDetail.project.blocked_task_count} detail="Needs coordination" tone="coral" onClick={() => openTasks("blocked")} />
                <MetricButton icon={MessageSquareText} label="Broadcasts" value={activeDetail.project.broadcast_count} detail="Project-wide" tone="blue" onClick={() => openProjectView("broadcasts")} />
                <MetricButton icon={KeyRound} label="Active leases" value={activeDetail.project.active_lease_count} detail="Shared resources" tone="plain" onClick={() => openProjectView("resources")} />
              </div>
            )}

            {projectIsLoading && <div className="metrics-skeleton metrics-skeleton--project" aria-label="Loading project summary" aria-busy="true"><span /><span /><span /><span /></div>}

            {error && <div className="error-banner"><AlertTriangle size={17} /><span>{error}</span><button type="button" onClick={() => { void refreshOverview(); void refreshVillage(); if (projectId) void refreshProject(projectId, true); if (projectId && view !== "overview") setViewRefreshVersion((current) => current + 1); }}>Retry</button></div>}
            {overviewLoading && !overview ? <div className="content-skeleton"><span /><span /><span /></div> : !overview ? null : !projectId ? (workspaceView === "directory" ? <DirectoryView directory={directory} loading={directoryLoading} error={directoryError} query={normalizedQuery} onRetry={() => { setDirectoryLoading(true); void refreshDirectory(); }} onProject={openProject} onAgent={openVillageAgent} /> : <WorkspaceOverview overview={overview} village={village} villageLoading={villageLoading} villageError={villageError} filter={workspaceFilter} query={normalizedQuery} onFilter={setWorkspaceFilter} onProject={openProject} onAgent={openVillageAgent} onBroadcast={openWorkspaceBroadcast} />) : projectIsLoading ? <div className="content-skeleton" aria-label="Loading project details" aria-busy="true"><span /><span /><span /></div> : projectContent}
          </div>
        </div>

        {selectedDay ? (
          <DaySummaryRail
            date={selectedDay}
            detail={dayDetail}
            loading={dayLoading}
            error={dayError}
            live={live}
            calendar={projectId ? activeDetail?.activity_calendar : overview?.activity_calendar}
            showProject={!projectId}
            onSelectDay={toggleDay}
            onClose={closeDay}
            onEvent={(event) => {
              if (projectId) handleActivity(event);
              else if (event.project_id) openProject(event.project_id);
            }}
          />
        ) : projectId ? activeDetail ? <ActivityRail events={activeDetail.activity} live={live} calendar={activeDetail.activity_calendar} selectedDay={selectedDay} onSelectDay={toggleDay} onEvent={handleActivity} /> : <ProjectActivityPlaceholder live={live} loading={projectIsLoading} /> : <WorkspaceBroadcastRail broadcasts={overview?.recent_broadcasts || []} live={live} calendar={overview?.activity_calendar} selectedDay={selectedDay} onSelectDay={toggleDay} onBroadcast={openWorkspaceBroadcast} />}
      </section>
      {selectedAgent && activeDetail && <AgentDrawer agent={selectedAgent} detail={selectedAgentDetail} loading={agentDetailLoading} onClose={closeAgent} onMessage={setSelectedMessage} onLoadMore={loadMoreAgentMessages} />}
      {selectedMessage && <MessageDrawer message={selectedMessage} projectName={projectNameForMessage} onClose={() => setSelectedMessage(null)} />}
    </main>
  );
}

export default function App() {
  const [auth, setAuth] = useState<"loading" | "authenticated" | "unauthenticated">("loading");

  useEffect(() => {
    getSession().then(() => setAuth("authenticated")).catch(() => setAuth("unauthenticated"));
  }, []);

  if (auth === "loading") return <LoadingScreen />;
  if (auth === "unauthenticated") return <LoginScreen onAuthenticated={() => setAuth("authenticated")} />;
  return <Dashboard onUnauthorized={() => setAuth("unauthenticated")} />;
}
