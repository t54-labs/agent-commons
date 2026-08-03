import Phaser from "phaser";
import { ChevronLeft, ChevronRight, Maximize2, Minimize2, ScanLine } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { Agent, Message, ProjectSummary, VillageProject, VillageSnapshot } from "./types";
import { footPointIsBlocked, VILLAGE_LEVEL, type MapPoint } from "./villageLevel";
import { navigationDiagnostics, planRandomPath, stationExitDiagnostics, type RandomPathState } from "./villageNavigation";

const PROJECTS_PER_DISTRICT = 6;
const MAX_VISIBLE_AGENTS_PER_PROJECT = 8;
const RECENT_MESSAGE_WINDOW_MS = 5 * 60 * 1000;
const MESSAGE_VISIBLE_MS = 6_400;
const MESSAGE_STAGGER_MS = 2_600;
const MAP_WIDTH = VILLAGE_LEVEL.map.width;
const MAP_HEIGHT = VILLAGE_LEVEL.map.height;
const AGENT_SPRITE_COUNT = 12;
const WALK_FRAMES_PER_DIRECTION = 4;
const WALK_FRAME_RATE = 8;
const WORLD_DEPTH_BASE = 100;
const ACTOR_UI_DEPTH_BASE = 12_000;
const HOVERED_ACTOR_UI_DEPTH = ACTOR_UI_DEPTH_BASE + MAP_HEIGHT + 1;
const AGENT_FOOT_RADIUS = 8;
const SPRITE_FOOT_OFFSET = 2;
const COLLISION_DEBUG_QUERY = "collisionDebug";
const VILLAGE_ASSET_VERSION = import.meta.env.VITE_VILLAGE_ASSET_VERSION || "development";

type Direction = "down" | "left" | "right" | "up";

const DIRECTIONS: Direction[] = ["down", "left", "right", "up"];
const DIRECTION_ROWS: Record<Direction, number> = {
  down: 0,
  left: 1,
  right: 2,
  up: 3,
};

type VillageProps = {
  snapshot: VillageSnapshot | null;
  fallbackProjects: ProjectSummary[];
  loading: boolean;
  error: string;
  onProject: (projectId: string) => void;
  onAgent: (projectId: string, agent: Agent) => void;
};

type MotionState = RandomPathState & {
  route: MapPoint[];
  destinationKey: string;
  x: number;
  y: number;
  targetIndex: number;
  waitRemaining: number;
  direction: Direction;
};

type MovementConfig = {
  motion: MotionState;
  mapX: number;
  mapY: number;
  sceneScale: number;
  speed: number;
};

type SceneActor = {
  container: Phaser.GameObjects.Container;
  uiElement: Phaser.GameObjects.DOMElement;
  sprite: Phaser.GameObjects.Sprite;
  spriteIndex: number;
  spriteScale: number;
  dust: Phaser.GameObjects.Graphics;
  sweat: Phaser.GameObjects.Graphics;
  statusElement: HTMLSpanElement | null;
  bubble: HTMLDivElement | null;
  profileElement: HTMLDivElement;
  profileWidth: number;
  bubbleStartedAt: number;
  bubbleAboveY: number;
  bubbleBelowY: number;
  uiScale: number;
  baseX: number;
  baseY: number;
  phase: number;
  working: boolean;
  blocked: boolean;
  hovered: boolean;
  roaming: boolean;
  moving: boolean;
  movement: MovementConfig | null;
};

type SceneForegroundLayer = {
  image: Phaser.GameObjects.Image;
  fadeWhenOccluded: boolean;
};

type SceneMetrics = {
  roamingAgentCount: number;
  actorCount: number;
  collisionBodyCount: number;
  foregroundObjectCount: number;
  blockedRouteCount: number;
  blockedSlotCount: number;
  navigationWalkableCellCount: number;
  navigationComponentCount: number;
  unauthorizedRoomExitCount: number;
};

type SceneBridge = {
  projects: () => VillageProject[];
  callbacks: () => Pick<VillageProps, "onProject" | "onAgent">;
  debugOverlay: () => boolean;
  messageFirstSeen: Map<string, number>;
  onReady: (metrics: SceneMetrics) => void;
  onNavigationSample: (destinationCount: number, uniqueDestinationCount: number) => void;
  onOcclusionSample: (fadedObjectCount: number) => void;
  onFailure: (message: string) => void;
  onFrameSample: (frame: string, direction: Direction) => void;
};

function assetUrl(path: string): string {
  const normalizedPath = path.replace(/^\//, "");
  return `/app/${normalizedPath}?v=${encodeURIComponent(VILLAGE_ASSET_VERSION)}`;
}

function actorUiDepth(y: number, hovered: boolean): number {
  return hovered ? HOVERED_ACTOR_UI_DEPTH : ACTOR_UI_DEPTH_BASE + Math.round(y);
}

function hashString(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function bubbleRendersBelow(actorY: number, uiScale: number): boolean {
  return actorY < Math.max(110, 132 * uiScale);
}

function truncate(value: string, length: number): string {
  const compact = value.replace(/\s+/g, " ").trim();
  return compact.length > length ? `${compact.slice(0, Math.max(1, length - 1))}...` : compact;
}

function agentName(agent: Agent): string {
  return agent.handle ? `@${agent.handle}` : agent.name || agent.agent_id;
}

function runtimeLabel(runtime: string): string {
  if (runtime === "claude-code") return "Claude Code";
  if (runtime === "codex") return "Codex";
  return runtime.replace(/[-_]+/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function workspaceLabel(workspace: string | null): string {
  if (!workspace) return "Not reported";
  const segments = workspace.replace(/\\/g, "/").split("/").filter(Boolean);
  return segments.at(-1) || workspace;
}

function deviceLabel(host: string | null): string {
  if (!host) return "Not reported";
  return host.replace(/\.local$/i, "");
}

function activityLabel(lastSeenSeconds: number): string {
  if (!Number.isFinite(lastSeenSeconds) || lastSeenSeconds < 0) return "Not reported";
  if (lastSeenSeconds < 60) return "Just now";
  if (lastSeenSeconds < 3_600) return `${Math.floor(lastSeenSeconds / 60)}m ago`;
  if (lastSeenSeconds < 86_400) return `${Math.floor(lastSeenSeconds / 3_600)}h ago`;
  return `${Math.floor(lastSeenSeconds / 86_400)}d ago`;
}

function agentStateLabel(agent: Agent): string {
  if (isBlocked(agent)) return "Blocked";
  if (isWorking(agent)) return "Working";
  if (agent.presence === "idle") return "Available";
  return agent.presence === "online" ? "Active" : "Offline";
}

function isWorking(agent: Agent): boolean {
  return agent.status === "busy" || Boolean(agent.current_task && !["completed", "cancelled", "failed"].includes(agent.current_task.status));
}

function isBlocked(agent: Agent): boolean {
  return Boolean(agent.current_task && ["blocked", "needs_human", "failed"].includes(agent.current_task.status));
}

function messageLabel(message: Message): string {
  if (message.recipient_agent_id) {
    const recipient = message.recipient_handle ? `@${message.recipient_handle}` : "an Agent";
    return `DM -> ${truncate(recipient, 18)}`;
  }
  return truncate(message.body, 60);
}

function latestMessagesBySender(messages: Message[]): Map<string, Message> {
  const result = new Map<string, Message>();
  const cutoff = Date.now() - RECENT_MESSAGE_WINDOW_MS;
  messages.forEach((message) => {
    if (!message.sender_agent_id || result.has(message.sender_agent_id)) return;
    const created = new Date(message.created_at).getTime();
    if (Number.isFinite(created) && created >= cutoff) result.set(message.sender_agent_id, message);
  });
  return result;
}

function rankProjects(projects: VillageProject[]): VillageProject[] {
  return [...projects].sort((left, right) => (
    right.project.active_agent_count - left.project.active_agent_count
    || right.project.last_activity_at.localeCompare(left.project.last_activity_at)
    || left.project.project_id.localeCompare(right.project.project_id)
  ));
}

function countBlockedAgentSlots(): number {
  return VILLAGE_LEVEL.stations.reduce(
    (count, station) => count + station.agentSlots.filter((slot) => footPointIsBlocked(slot, AGENT_FOOT_RADIUS)).length,
    0,
  );
}

function toScreen(point: MapPoint, mapX: number, mapY: number, sceneScale: number): MapPoint {
  return {
    x: mapX + point.x * sceneScale,
    y: mapY + point.y * sceneScale,
  };
}

function animationKey(spriteIndex: number, direction: Direction): string {
  return `agent-${String(spriteIndex).padStart(2, "0")}-walk-${direction}`;
}

function objectTextureKey(asset: string): string {
  return `village-object-${asset.replace(/[^a-z0-9]+/gi, "-")}`;
}

class CommonsVillageScene extends Phaser.Scene {
  private readonly bridge: SceneBridge;
  private readonly motionStates = new Map<string, MotionState>();
  private actors: SceneActor[] = [];
  private foregroundLayers: SceneForegroundLayer[] = [];
  private ready = false;
  private loadFailed = false;
  private elapsed = 0;
  private lastFrameSample = "";
  private lastNavigationSample = "";
  private lastOcclusionSample = -1;

  constructor(bridge: SceneBridge) {
    super({ key: "commons-village" });
    this.bridge = bridge;
  }

  preload(): void {
    this.load.on("loaderror", () => {
      this.loadFailed = true;
      this.bridge.onFailure("A pixel village asset could not be loaded.");
    });
    this.load.image("commons-village-map", assetUrl(VILLAGE_LEVEL.map.asset));
    new Set(VILLAGE_LEVEL.objects.map((object) => object.asset)).forEach((asset) => {
      this.load.image(objectTextureKey(asset), assetUrl(asset));
    });
    for (let index = 0; index < AGENT_SPRITE_COUNT; index += 1) {
      const suffix = String(index).padStart(2, "0");
      this.load.spritesheet(`agent-walk-${suffix}`, assetUrl(`village/walk/agent-${suffix}.png`), {
        frameWidth: 64,
        frameHeight: 80,
      });
    }
  }

  create(): void {
    if (this.loadFailed) return;
    this.registerAnimations();
    this.ready = true;
    this.rebuild();
  }

  refresh(): void {
    if (this.ready) this.rebuild();
  }

  update(_time: number, delta: number): void {
    if (!this.ready) return;
    const deltaSeconds = Math.min(delta / 1000, 0.05);
    this.elapsed += deltaSeconds;
    const now = Date.now();
    let sampled = false;
    this.actors.forEach((actor) => {
      actor.moving = this.advanceActorMotion(actor, deltaSeconds);
      actor.uiElement
        .setPosition(actor.container.x, actor.container.y)
        .setDepth(actorUiDepth(actor.container.y, actor.hovered));
      const direction = actor.movement?.motion.direction || "down";
      if (actor.moving) {
        const key = animationKey(actor.spriteIndex, direction);
        actor.sprite.play(key, true);
        actor.sprite.setY(SPRITE_FOOT_OFFSET * actor.spriteScale);
        actor.dust.setAlpha(0.32 + Math.abs(Math.sin(this.elapsed * 11 + actor.phase)) * 0.38);
        actor.dust.setX(direction === "left" ? 7 * actor.uiScale : direction === "right" ? -7 * actor.uiScale : 0);
        actor.sweat.setAlpha(0);
        if (!sampled) {
          const frame = String(actor.sprite.frame.name);
          if (frame !== this.lastFrameSample) {
            this.lastFrameSample = frame;
            this.bridge.onFrameSample(frame, direction);
          }
          sampled = true;
        }
      } else {
        const idleFrame = DIRECTION_ROWS[direction] * WALK_FRAMES_PER_DIRECTION;
        actor.sprite.stop();
        actor.sprite.setFrame(idleFrame);
        const wave = Math.sin(this.elapsed * (actor.working ? 6.6 : 1.3) + actor.phase);
        actor.sprite.setY(
          SPRITE_FOOT_OFFSET * actor.spriteScale + (actor.working ? Math.round(wave * 0.7) : wave * 0.3),
        );
        actor.dust.setAlpha(0);
        actor.sweat.setAlpha(actor.working ? 0.45 + Math.max(0, wave) * 0.55 : 0);
        actor.sweat.setY(-67 * actor.sprite.scaleY + ((this.elapsed * 9 + actor.phase) % 6));
      }
      actor.sprite.setScale(actor.spriteScale * (actor.hovered ? 1.06 : 1));
      if (actor.statusElement) {
        const wave = Math.sin(this.elapsed * 5 + actor.phase);
        actor.statusElement.style.opacity = String(
          actor.blocked ? 0.7 + Math.max(0, wave) * 0.3 : 0.72 + Math.max(0, wave) * 0.28,
        );
      }
      this.positionAgentProfile(actor);
      this.updateBubble(actor, now);
    });
    this.updateForegroundOcclusion();
    const destinationCount = this.actors.reduce((count, actor) => count + (actor.movement?.motion.destinationCount || 0), 0);
    const uniqueDestinationCount = new Set(
      this.actors.flatMap((actor) => actor.movement?.motion.recentDestinationKeys || []),
    ).size;
    const navigationSample = `${destinationCount}:${uniqueDestinationCount}`;
    if (navigationSample !== this.lastNavigationSample) {
      this.lastNavigationSample = navigationSample;
      this.bridge.onNavigationSample(destinationCount, uniqueDestinationCount);
    }
  }

  private registerAnimations(): void {
    for (let index = 0; index < AGENT_SPRITE_COUNT; index += 1) {
      const suffix = String(index).padStart(2, "0");
      const textureKey = `agent-walk-${suffix}`;
      DIRECTIONS.forEach((direction) => {
        const key = animationKey(index, direction);
        if (this.anims.exists(key)) return;
        const start = DIRECTION_ROWS[direction] * WALK_FRAMES_PER_DIRECTION;
        this.anims.create({
          key,
          frames: this.anims.generateFrameNumbers(textureKey, {
            start,
            end: start + WALK_FRAMES_PER_DIRECTION - 1,
          }),
          frameRate: WALK_FRAME_RATE,
          repeat: -1,
          skipMissedFrames: true,
        });
      });
    }
  }

  private rebuild(): void {
    this.children.removeAll(true);
    if (this.game.domContainer) {
      this.game.domContainer.replaceChildren();
      this.game.domContainer.style.setProperty("pointer-events", "none", "important");
    }
    this.actors = [];
    this.foregroundLayers = [];
    const width = Math.max(320, this.scale.width);
    const height = Math.max(180, this.scale.height);
    const sceneScale = Math.max(width / MAP_WIDTH, height / MAP_HEIGHT);
    const mapX = (width - MAP_WIDTH * sceneScale) / 2;
    const mapY = (height - MAP_HEIGHT * sceneScale) / 2;
    const uiScale = clamp(width / 1080, 0.72, 1.15);
    const spriteScale = clamp(sceneScale, 0.58, 0.92);
    const blockedRouteCount = 0;
    const blockedSlotCount = countBlockedAgentSlots();
    const collisionBodyCount = [...VILLAGE_LEVEL.objects, ...VILLAGE_LEVEL.boundaries]
      .reduce((count, item) => count + item.collisionPolygons.length, 0);
    const navigation = navigationDiagnostics();
    const unauthorizedRoomExitCount = stationExitDiagnostics()
      .reduce((count, diagnostic) => count + diagnostic.unauthorizedTransitionCount, 0);

    this.add.image(mapX, mapY, "commons-village-map").setOrigin(0).setScale(sceneScale).setDepth(0);
    const foregroundObjectCount = this.createForegroundObjectLayers(mapX, mapY, sceneScale);
    if (this.bridge.debugOverlay()) this.createDebugOverlay(mapX, mapY, sceneScale);

    const projects = this.bridge.projects();

    const currentMessageIds = new Set(projects.flatMap((projectData) => projectData.recent_messages.map((message) => message.message_id)));
    this.bridge.messageFirstSeen.forEach((_, messageId) => {
      if (!currentMessageIds.has(messageId)) this.bridge.messageFirstSeen.delete(messageId);
    });

    if (!projects.length) {
      this.motionStates.clear();
      const emptyNode = document.createElement("div");
      emptyNode.className = "village-empty-state";
      emptyNode.textContent = "The village is quiet. Active Projects will gather here.";
      emptyNode.style.width = `${clamp(370 * uiScale, 260, 420)}px`;
      this.add.dom(width / 2, height / 2, emptyNode).setOrigin(0.5).setDepth(ACTOR_UI_DEPTH_BASE);
      this.add.rectangle(width / 2, Math.max(48, 64 * uiScale) / 2, width, Math.max(48, 64 * uiScale), 0x0c3233, 0.76).setDepth(20_000);
      this.bridge.onReady({
        roamingAgentCount: 0,
        actorCount: 0,
        collisionBodyCount,
        foregroundObjectCount,
        blockedRouteCount,
        blockedSlotCount,
        navigationWalkableCellCount: navigation.walkableCellCount,
        navigationComponentCount: navigation.componentCount,
        unauthorizedRoomExitCount,
      });
      return;
    }

    const spriteIndexByAgent = this.assignSpriteIndexes(projects);
    const roamingAgentKeys = this.selectRoamingAgents(projects);
    let bubbleOrder = 0;

    projects.forEach((projectData, projectIndex) => {
      const station = VILLAGE_LEVEL.stations[projectIndex];
      const center = toScreen(station.center, mapX, mapY, sceneScale);
      const centerX = center.x;
      const centerY = center.y;
      const zoneWidth = 0.24 * MAP_WIDTH * sceneScale;
      const zoneHeight = 0.30 * MAP_HEIGHT * sceneScale;
      const sign = toScreen(station.sign, mapX, mapY, sceneScale);
      const topBarHeight = Math.max(48, 64 * uiScale);
      this.createProjectZone(projectData, centerX, centerY, Math.max(sign.y, topBarHeight + 18), zoneWidth, zoneHeight, uiScale);

      const messages = latestMessagesBySender(projectData.recent_messages);
      projectData.agents.slice(0, MAX_VISIBLE_AGENTS_PER_PROJECT).forEach((agent, agentIndex) => {
        const agentKey = `${agent.project_id}:${agent.agent_id}`;
        const seed = hashString(`${agentKey}:${agent.handle || ""}`);
        const slot = station.agentSlots[agentIndex % station.agentSlots.length];
        const agentPosition = toScreen(slot, mapX, mapY, sceneScale);
        const agentX = agentPosition.x;
        const agentY = agentPosition.y;
        const message = messages.get(agent.agent_id);
        let bubbleStartedAt = 0;
        if (message) {
          bubbleStartedAt = this.bridge.messageFirstSeen.get(message.message_id) || Date.now() + bubbleOrder * MESSAGE_STAGGER_MS;
          this.bridge.messageFirstSeen.set(message.message_id, bubbleStartedAt);
          bubbleOrder += 1;
        }

        let movement: MovementConfig | null = null;
        if (roamingAgentKeys.has(agentKey)) {
          let motion = this.motionStates.get(agentKey);
          if (!motion) {
            const initialPlan = planRandomPath(slot, {
              randomState: seed || 1,
              recentDestinationKeys: [],
              destinationCount: 0,
            });
            if (initialPlan) {
              const start = initialPlan.points[0];
              motion = {
                route: initialPlan.points,
                destinationKey: initialPlan.destinationKey,
                randomState: initialPlan.randomState,
                recentDestinationKeys: initialPlan.recentDestinationKeys,
                destinationCount: initialPlan.destinationCount,
                x: start.x,
                y: start.y,
                targetIndex: 1,
                waitRemaining: 0.2 + (seed % 8) / 10,
                direction: "down",
              };
              this.motionStates.set(agentKey, motion);
            }
          }
          if (motion) {
            movement = {
              motion,
              mapX,
              mapY,
              sceneScale,
              speed: clamp(55 * sceneScale * (0.86 + (seed % 15) / 100), 18, 48),
            };
          } else {
            this.motionStates.delete(agentKey);
          }
        }

        const actor = this.createActor({
          agent,
          spriteIndex: spriteIndexByAgent.get(agentKey) ?? 0,
          x: agentX,
          y: agentY,
          spriteScale,
          uiScale,
          message,
          bubbleStartedAt,
          bubbleShift: agentX < width * 0.18 ? 32 * uiScale : agentX > width * 0.82 ? -32 * uiScale : 0,
          movement,
          onSelect: () => this.bridge.callbacks().onAgent(projectData.project.project_id, agent),
        });
        this.actors.push(actor);
      });

      const hiddenAgents = Math.max(0, projectData.project.active_agent_count - Math.min(projectData.agents.length, MAX_VISIBLE_AGENTS_PER_PROJECT));
      if (hiddenAgents > 0 || projectData.has_more_agents) {
        const x = centerX + zoneWidth * 0.35;
        const y = centerY + zoneHeight * 0.37;
        const hiddenNode = document.createElement("div");
        hiddenNode.className = "village-hidden-count";
        hiddenNode.textContent = `+${hiddenAgents || "more"}`;
        this.add.dom(x, y, hiddenNode).setOrigin(0.5).setDepth(ACTOR_UI_DEPTH_BASE);
      }
    });

    this.motionStates.forEach((_, agentKey) => {
      if (!roamingAgentKeys.has(agentKey)) this.motionStates.delete(agentKey);
    });

    this.add.rectangle(width / 2, Math.max(48, 64 * uiScale) / 2, width, Math.max(48, 64 * uiScale), 0x0c3233, 0.76).setDepth(20_000);
    this.bridge.onReady({
      roamingAgentCount: this.actors.filter((actor) => actor.roaming).length,
      actorCount: this.actors.length,
      collisionBodyCount,
      foregroundObjectCount,
      blockedRouteCount,
      blockedSlotCount,
      navigationWalkableCellCount: navigation.walkableCellCount,
      navigationComponentCount: navigation.componentCount,
      unauthorizedRoomExitCount,
    });
  }

  private createForegroundObjectLayers(mapX: number, mapY: number, sceneScale: number): number {
    VILLAGE_LEVEL.objects.forEach((object) => {
      const position = toScreen(object.position, mapX, mapY, sceneScale);
      const depthY = mapY + object.depthY * sceneScale;
      const image = this.add.image(position.x, position.y, objectTextureKey(object.asset))
        .setOrigin(0.5, 1)
        .setScale(sceneScale)
        .setDepth(WORLD_DEPTH_BASE + Math.round(depthY));
      this.foregroundLayers.push({ image, fadeWhenOccluded: object.fadeWhenOccluded });
    });
    return VILLAGE_LEVEL.objects.length;
  }

  private createDebugOverlay(mapX: number, mapY: number, sceneScale: number): void {
    const graphics = this.add.graphics().setDepth(WORLD_DEPTH_BASE + MAP_HEIGHT + 10);
    const screenPolygon = (polygon: readonly MapPoint[]) => polygon.map((point) => (
      new Phaser.Math.Vector2(mapX + point.x * sceneScale, mapY + point.y * sceneScale)
    ));

    graphics.lineStyle(1.5, 0x55e8a5, 0.72);
    VILLAGE_LEVEL.navigation.walkablePolygons.forEach((polygon) => {
      graphics.strokePoints(screenPolygon(polygon), true);
    });

    VILLAGE_LEVEL.objects.forEach((object) => {
      object.collisionPolygons.forEach((polygon) => {
        const points = screenPolygon(polygon);
        graphics.fillStyle(0xffd65c, 0.16).fillPoints(points, true);
        graphics.lineStyle(2, 0xffd65c, 0.95).strokePoints(points, true);
      });
    });

    VILLAGE_LEVEL.boundaries.forEach((boundary) => {
      boundary.collisionPolygons.forEach((polygon) => {
        const points = screenPolygon(polygon);
        graphics.fillStyle(0xff4f91, 0.2).fillPoints(points, true);
        graphics.lineStyle(2, 0xff4f91, 1).strokePoints(points, true);
      });
    });

    graphics.lineStyle(4, 0x5fffe2, 1);
    VILLAGE_LEVEL.portals.forEach((portal) => {
      const inside = toScreen(portal.inside, mapX, mapY, sceneScale);
      const outside = toScreen(portal.outside, mapX, mapY, sceneScale);
      graphics.lineBetween(inside.x, inside.y, outside.x, outside.y);
      graphics.fillStyle(0x5fffe2, 1).fillCircle(inside.x, inside.y, 4);
      graphics.fillCircle(outside.x, outside.y, 4);
    });
  }

  private updateForegroundOcclusion(): void {
    let fadedObjectCount = 0;
    this.foregroundLayers.forEach((layer) => {
      const bounds = layer.image.getBounds();
      const occludesActor = layer.fadeWhenOccluded && this.actors.some((actor) => {
        if (actor.container.depth >= layer.image.depth) return false;
        const actorBounds = new Phaser.Geom.Rectangle(
          actor.container.x - 19 * actor.spriteScale,
          actor.container.y - 72 * actor.spriteScale,
          38 * actor.spriteScale,
          74 * actor.spriteScale,
        );
        return Phaser.Geom.Intersects.RectangleToRectangle(bounds, actorBounds);
      });
      const targetAlpha = occludesActor ? 0.38 : 1;
      layer.image.setAlpha(Phaser.Math.Linear(layer.image.alpha, targetAlpha, 0.24));
      if (occludesActor) fadedObjectCount += 1;
    });
    if (fadedObjectCount !== this.lastOcclusionSample) {
      this.lastOcclusionSample = fadedObjectCount;
      this.bridge.onOcclusionSample(fadedObjectCount);
    }
  }

  private assignSpriteIndexes(projects: VillageProject[]): Map<string, number> {
    const result = new Map<string, number>();
    const used = new Set<number>();
    const visibleAgents = projects
      .flatMap((projectData) => projectData.agents.slice(0, MAX_VISIBLE_AGENTS_PER_PROJECT))
      .sort((left, right) => `${left.project_id}:${left.agent_id}`.localeCompare(`${right.project_id}:${right.agent_id}`));
    visibleAgents.forEach((agent) => {
      const key = `${agent.project_id}:${agent.agent_id}`;
      const preferred = hashString(`${key}:${agent.handle || ""}`) % AGENT_SPRITE_COUNT;
      let index = preferred;
      for (let offset = 0; offset < AGENT_SPRITE_COUNT; offset += 1) {
        const candidate = (preferred + offset) % AGENT_SPRITE_COUNT;
        if (!used.has(candidate)) {
          index = candidate;
          break;
        }
      }
      result.set(key, index);
      used.add(index);
    });
    return result;
  }

  private selectRoamingAgents(projects: VillageProject[]): Set<string> {
    const result = new Set<string>();
    projects.forEach((projectData) => {
      const candidates = projectData.agents
        .slice(0, MAX_VISIBLE_AGENTS_PER_PROJECT)
        .filter((agent) => !isWorking(agent) && !isBlocked(agent) && agent.presence !== "offline");
      candidates.forEach((agent) => result.add(`${agent.project_id}:${agent.agent_id}`));
    });
    return result;
  }

  private createProjectZone(
    projectData: VillageProject,
    centerX: number,
    centerY: number,
    signY: number,
    zoneWidth: number,
    zoneHeight: number,
    uiScale: number,
  ): void {
    const focus = this.add.rectangle(centerX, centerY, zoneWidth, zoneHeight, 0xfff4c4, 0.08)
      .setStrokeStyle(2, 0xffe36e, 0.78)
      .setVisible(false)
      .setDepth(10);
    const sign = this.createProjectSign(projectData, centerX, signY, uiScale);
    const zone = this.add.zone(centerX, centerY, zoneWidth, zoneHeight).setInteractive({ useHandCursor: true }).setDepth(20);
    zone.on("pointerover", () => {
      focus.setVisible(true);
      sign.setY(signY - 2 * uiScale);
    });
    zone.on("pointerout", () => {
      focus.setVisible(false);
      sign.setY(signY);
    });
    zone.on("pointerup", () => this.bridge.callbacks().onProject(projectData.project.project_id));
  }

  private createProjectSign(projectData: VillageProject, x: number, y: number, uiScale: number): Phaser.GameObjects.DOMElement {
    const node = document.createElement("div");
    node.className = "village-project-sign";
    node.style.setProperty("--project-sign-min-width", `${clamp(100 * uiScale, 76, 116)}px`);
    node.style.setProperty("--project-name-size", `${clamp(12.5 * uiScale, 8.5, 15)}px`);
    node.style.setProperty("--project-count-size", `${clamp(11 * uiScale, 7.5, 13)}px`);

    const name = document.createElement("strong");
    name.textContent = truncate(projectData.project.display_name, 24);
    const count = document.createElement("span");
    count.textContent = `${projectData.project.active_agent_count} active`;
    node.append(name, count);

    return this.add.dom(x, y, node).setOrigin(0.5).setDepth(10_000);
  }

  private createActor(config: {
    agent: Agent;
    spriteIndex: number;
    x: number;
    y: number;
    spriteScale: number;
    uiScale: number;
    message: Message | undefined;
    bubbleStartedAt: number;
    bubbleShift: number;
    movement: MovementConfig | null;
    onSelect: () => void;
  }): SceneActor {
    const { agent, spriteIndex, spriteScale, uiScale, movement } = config;
    const seed = hashString(`${agent.project_id}:${agent.agent_id}:${agent.handle || ""}`);
    const initial = movement ? toScreen(movement.motion, movement.mapX, movement.mapY, movement.sceneScale) : { x: config.x, y: config.y };
    const textureKey = `agent-walk-${String(spriteIndex).padStart(2, "0")}`;

    const shadow = this.add.ellipse(
      0,
      1 * spriteScale,
      30 * spriteScale,
      6 * spriteScale,
      0x173334,
      0.38,
    );
    const dust = this.add.graphics();
    dust.fillStyle(0xe9d6a0, 1).fillRect(-9 * uiScale, -2 * uiScale, 4 * uiScale, 3 * uiScale);
    dust.fillStyle(0xffebbd, 1).fillRect(6 * uiScale, -4 * uiScale, 3 * uiScale, 3 * uiScale);
    dust.setAlpha(0);
    const sprite = this.add.sprite(0, SPRITE_FOOT_OFFSET * spriteScale, textureKey, 0).setOrigin(0.5, 1).setScale(spriteScale);
    const sweat = this.add.graphics();
    sweat.fillStyle(0x8de9f2, 1).fillRect(20 * spriteScale, 0, 3 * uiScale, 6 * uiScale);
    sweat.fillStyle(0xc4f7fa, 1).fillRect(25 * spriteScale, 6 * uiScale, 2 * uiScale, 4 * uiScale);
    sweat.setY(-67 * spriteScale).setAlpha(isWorking(agent) ? 1 : 0);

    const uiNode = document.createElement("div");
    uiNode.className = "village-agent-ui";
    uiNode.dataset.agentId = agent.agent_id;

    let statusElement: HTMLSpanElement | null = null;
    if (isBlocked(agent)) {
      statusElement = document.createElement("span");
      statusElement.className = "village-agent-ui__status village-agent-ui__status--blocked";
      statusElement.textContent = "!";
      statusElement.style.left = `${-21 * spriteScale}px`;
      statusElement.style.top = `${-76 * spriteScale}px`;
    } else if (!movement && !isWorking(agent) && agent.presence === "idle") {
      statusElement = document.createElement("span");
      statusElement.className = "village-agent-ui__status village-agent-ui__status--idle";
      statusElement.textContent = "z";
      statusElement.style.left = `${16 * spriteScale}px`;
      statusElement.style.top = `${-71 * spriteScale}px`;
    }

    const shortName = truncate((agent.handle || agent.name || agent.agent_id).replace(/^@/, ""), 14);
    const namePlate = document.createElement("span");
    namePlate.className = "village-agent-ui__name";
    namePlate.textContent = shortName;
    namePlate.style.top = `${5 * uiScale}px`;
    namePlate.style.fontSize = `${clamp(11.5 * uiScale, 7.5, 13.5)}px`;
    const bubbleAboveY = -80 * spriteScale - 8 * uiScale;
    const bubbleBelowY = 74 * spriteScale;
    const bubble = config.message
      ? this.createSpeechBubble(messageLabel(config.message), config.bubbleShift, bubbleRendersBelow(initial.y, uiScale) ? bubbleBelowY : bubbleAboveY, uiScale)
      : null;
    const profileWidth = clamp(220 * uiScale, 184, 244);
    const profile = this.createAgentProfile(agent, profileWidth, uiScale);
    const hoverTarget = document.createElement("button");
    hoverTarget.type = "button";
    hoverTarget.className = "village-agent-ui__hitbox";
    hoverTarget.setAttribute("aria-label", `Preview ${agentName(agent)}`);
    hoverTarget.setAttribute("aria-describedby", profile.id);
    hoverTarget.style.left = `${-32 * spriteScale}px`;
    hoverTarget.style.top = `${-80 * spriteScale}px`;
    hoverTarget.style.width = `${64 * spriteScale}px`;
    hoverTarget.style.height = `${86 * spriteScale}px`;

    if (statusElement) uiNode.append(statusElement);
    uiNode.append(namePlate, profile, hoverTarget);
    if (bubble) uiNode.append(bubble);

    const container = this.add.container(initial.x, initial.y, [shadow, dust, sprite, sweat])
      .setDepth(WORLD_DEPTH_BASE + Math.round(initial.y));
    const uiElement = this.add.dom(initial.x, initial.y, uiNode)
      .setOrigin(0, 0)
      .setDepth(actorUiDepth(initial.y, false));
    const actor: SceneActor = {
      container,
      uiElement,
      sprite,
      spriteIndex,
      spriteScale,
      dust,
      sweat,
      statusElement,
      bubble,
      profileElement: profile,
      profileWidth,
      bubbleStartedAt: config.bubbleStartedAt,
      bubbleAboveY,
      bubbleBelowY,
      uiScale,
      baseX: initial.x,
      baseY: initial.y,
      phase: (seed % 628) / 100,
      working: isWorking(agent),
      blocked: isBlocked(agent),
      hovered: false,
      roaming: Boolean(movement),
      moving: false,
      movement,
    };
    const setHovered = (hovered: boolean) => {
      actor.hovered = hovered;
      actor.uiElement.setDepth(actorUiDepth(actor.container.y, hovered));
      uiNode.classList.toggle("village-agent-ui--hovered", hovered);
      profile.classList.toggle("village-agent-ui__profile--visible", hovered);
      profile.setAttribute("aria-hidden", String(!hovered));
    };
    hoverTarget.addEventListener("pointerenter", () => {
      this.input.enabled = false;
      setHovered(true);
    });
    hoverTarget.addEventListener("pointerleave", () => {
      this.input.enabled = true;
      setHovered(false);
    });
    hoverTarget.addEventListener("focus", () => setHovered(true));
    hoverTarget.addEventListener("blur", () => setHovered(false));
    hoverTarget.addEventListener("pointerdown", (event) => {
      this.input.enabled = false;
      event.preventDefault();
      event.stopPropagation();
    });
    hoverTarget.addEventListener("pointerup", (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
    hoverTarget.addEventListener("click", (event) => {
      event.stopPropagation();
      config.onSelect();
    });
    this.positionAgentProfile(actor);
    return actor;
  }

  private createAgentProfile(agent: Agent, width: number, uiScale: number): HTMLDivElement {
    const profile = document.createElement("div");
    profile.id = `village-agent-profile-${hashString(`${agent.project_id}:${agent.agent_id}`)}`;
    profile.className = "village-agent-ui__profile";
    profile.setAttribute("role", "tooltip");
    profile.setAttribute("aria-hidden", "true");
    profile.style.width = `${width}px`;
    profile.style.setProperty("--profile-font-size", `${clamp(10.5 * uiScale, 9, 12)}px`);

    const header = document.createElement("div");
    header.className = "village-agent-ui__profile-header";
    const identity = document.createElement("div");
    const handle = document.createElement("strong");
    handle.textContent = agentName(agent);
    handle.title = agentName(agent);
    const state = document.createElement("span");
    state.className = `village-agent-ui__profile-state village-agent-ui__profile-state--${agentStateLabel(agent).toLowerCase()}`;
    state.textContent = agentStateLabel(agent);
    identity.append(handle, state);
    const contact = document.createElement("span");
    contact.className = "village-agent-ui__profile-contact";
    contact.textContent = agent.contact_code || "No code";
    header.append(identity, contact);

    const details = document.createElement("dl");
    details.className = "village-agent-ui__profile-details";
    const addDetail = (label: string, value: string) => {
      const row = document.createElement("div");
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = label;
      description.textContent = value;
      description.title = value;
      row.append(term, description);
      details.append(row);
    };
    addDetail("Owner", agent.user_name || "Unattributed");
    addDetail("Device", deviceLabel(agent.host));
    addDetail("Runtime", runtimeLabel(agent.runtime));
    addDetail("Workspace", workspaceLabel(agent.workspace));
    addDetail("Last seen", activityLabel(agent.last_seen_seconds));

    const work = document.createElement("div");
    work.className = "village-agent-ui__profile-work";
    const workLabel = document.createElement("span");
    workLabel.textContent = "Current work";
    const workTitle = document.createElement("strong");
    workTitle.textContent = agent.current_task?.title || (isWorking(agent) ? "Busy, no task reported" : "Available for work");
    workTitle.title = workTitle.textContent;
    work.append(workLabel, workTitle);
    profile.append(header, details, work);
    return profile;
  }

  private positionAgentProfile(actor: SceneActor): void {
    const profile = actor.profileElement;
    const below = actor.container.y < this.scale.height * 0.52;
    const edge = actor.profileWidth / 2 + 14;
    const alignment = actor.container.x < edge
      ? "left"
      : actor.container.x > this.scale.width - edge
        ? "right"
        : "center";
    profile.classList.toggle("village-agent-ui__profile--below", below);
    profile.classList.toggle("village-agent-ui__profile--left", alignment === "left");
    profile.classList.toggle("village-agent-ui__profile--right", alignment === "right");
    profile.style.left = alignment === "left"
      ? `${-24 * actor.spriteScale}px`
      : alignment === "right"
        ? `${24 * actor.spriteScale}px`
        : "0";
    profile.style.top = `${below ? 76 * actor.spriteScale : -86 * actor.spriteScale}px`;
  }

  private createSpeechBubble(copy: string, shift: number, baseY: number, uiScale: number): HTMLDivElement {
    const bubble = document.createElement("div");
    bubble.className = `village-agent-ui__bubble${baseY > 0 ? " village-agent-ui__bubble--below" : ""}`;
    bubble.textContent = copy;
    bubble.style.left = `${shift}px`;
    bubble.style.top = `${baseY}px`;
    bubble.style.width = `${clamp(148 * uiScale, 90, 184)}px`;
    bubble.style.fontSize = `${clamp(12.5 * uiScale, 8.5, 14)}px`;
    return bubble;
  }

  private advanceActorMotion(actor: SceneActor, deltaSeconds: number): boolean {
    const movement = actor.movement;
    if (!movement) {
      actor.container.setPosition(actor.baseX, actor.baseY).setDepth(WORLD_DEPTH_BASE + Math.round(actor.baseY));
      return false;
    }
    const { motion } = movement;
    const current = toScreen(motion, movement.mapX, movement.mapY, movement.sceneScale);
    actor.container.setPosition(current.x, current.y).setDepth(WORLD_DEPTH_BASE + Math.round(current.y));
    if (motion.waitRemaining > 0) {
      motion.waitRemaining = Math.max(0, motion.waitRemaining - deltaSeconds);
      return false;
    }

    const target = motion.route[motion.targetIndex];
    if (!target) {
      const recovery = planRandomPath(motion, motion);
      if (!recovery) return false;
      motion.route = recovery.points;
      motion.destinationKey = recovery.destinationKey;
      motion.randomState = recovery.randomState;
      motion.recentDestinationKeys = recovery.recentDestinationKeys;
      motion.destinationCount = recovery.destinationCount;
      motion.targetIndex = 1;
      return false;
    }
    const targetScreen = toScreen(target, movement.mapX, movement.mapY, movement.sceneScale);
    const deltaX = targetScreen.x - current.x;
    const deltaY = targetScreen.y - current.y;
    const distance = Math.hypot(deltaX, deltaY);
    const travel = movement.speed * deltaSeconds;
    if (distance <= Math.max(1, travel)) {
      motion.x = target.x;
      motion.y = target.y;
      if (motion.targetIndex >= motion.route.length - 1) {
        const nextPlan = planRandomPath(motion, motion);
        if (nextPlan) {
          motion.route = nextPlan.points;
          motion.destinationKey = nextPlan.destinationKey;
          motion.randomState = nextPlan.randomState;
          motion.recentDestinationKeys = nextPlan.recentDestinationKeys;
          motion.destinationCount = nextPlan.destinationCount;
          motion.targetIndex = 1;
        }
        motion.waitRemaining = 0.65 + (actor.phase % 1.15);
      } else {
        motion.targetIndex += 1;
        motion.waitRemaining = 0.08 + (actor.phase % 0.18);
      }
      const snapped = toScreen(motion, movement.mapX, movement.mapY, movement.sceneScale);
      actor.container.setPosition(snapped.x, snapped.y).setDepth(WORLD_DEPTH_BASE + Math.round(snapped.y));
      return false;
    }

    if (Math.abs(deltaX) > Math.abs(deltaY) * 0.82) motion.direction = deltaX < 0 ? "left" : "right";
    else motion.direction = deltaY < 0 ? "up" : "down";
    const ratio = travel / distance;
    const candidate = {
      x: motion.x + (target.x - motion.x) * ratio,
      y: motion.y + (target.y - motion.y) * ratio,
    };
    if (footPointIsBlocked(candidate, AGENT_FOOT_RADIUS)) {
      const recovery = planRandomPath(motion, motion);
      if (recovery) {
        motion.route = recovery.points;
        motion.destinationKey = recovery.destinationKey;
        motion.randomState = recovery.randomState;
        motion.recentDestinationKeys = recovery.recentDestinationKeys;
        motion.destinationCount = recovery.destinationCount;
        motion.targetIndex = 1;
      }
      motion.waitRemaining = 0.8;
      return false;
    }
    motion.x = candidate.x;
    motion.y = candidate.y;
    const next = toScreen(motion, movement.mapX, movement.mapY, movement.sceneScale);
    actor.container.setPosition(next.x, next.y).setDepth(WORLD_DEPTH_BASE + Math.round(next.y));
    return true;
  }

  private updateBubble(actor: SceneActor, now: number): void {
    if (!actor.bubble) return;
    const age = now - actor.bubbleStartedAt;
    if (age < 0 || age >= MESSAGE_VISIBLE_MS) {
      actor.bubble.style.opacity = "0";
      return;
    }
    const enter = Math.min(1, age / 220);
    const exit = age > MESSAGE_VISIBLE_MS - 950 ? Math.max(0, (MESSAGE_VISIBLE_MS - age) / 950) : 1;
    const scale = 0.82 + enter * 0.18;
    const baseY = bubbleRendersBelow(actor.container.y, actor.uiScale) ? actor.bubbleBelowY : actor.bubbleAboveY;
    const wave = Math.sin(this.elapsed * 2.4 + actor.phase) * 1.5;
    const below = baseY > 0;
    actor.bubble.classList.toggle("village-agent-ui__bubble--below", below);
    actor.bubble.style.top = `${baseY}px`;
    actor.bubble.style.opacity = String(Math.min(enter, exit));
    actor.bubble.style.transform = `translate(-50%, ${below ? "0" : "-100%"}) translateY(${wave}px) scale(${scale})`;
  }
}

export default function AgentVillage({ snapshot, fallbackProjects, loading, error, onProject, onAgent }: VillageProps) {
  const collisionDebugAvailable = typeof window !== "undefined"
    && new URLSearchParams(window.location.search).get(COLLISION_DEBUG_QUERY) === "1";
  const villageRef = useRef<HTMLElement | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<CommonsVillageScene | null>(null);
  const visibleProjectsRef = useRef<VillageProject[]>([]);
  const callbacksRef = useRef({ onProject, onAgent });
  const messageFirstSeenRef = useRef(new Map<string, number>());
  const debugOverlayRef = useRef(collisionDebugAvailable);
  const [rendererState, setRendererState] = useState<"loading" | "ready" | "failed">("loading");
  const [districtPage, setDistrictPage] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const [debugOverlay, setDebugOverlay] = useState<boolean>(collisionDebugAvailable);

  callbacksRef.current = { onProject, onAgent };
  debugOverlayRef.current = debugOverlay;

  const accessibleProjects = useMemo(
    () => snapshot?.projects || fallbackProjects.map((project) => ({ project, agents: [], recent_messages: [], has_more_agents: false })),
    [fallbackProjects, snapshot],
  );
  const rankedProjects = useMemo(() => rankProjects(accessibleProjects), [accessibleProjects]);
  const districtCount = Math.max(1, Math.ceil(rankedProjects.length / PROJECTS_PER_DISTRICT));
  const visibleProjects = useMemo(
    () => rankedProjects.slice(districtPage * PROJECTS_PER_DISTRICT, (districtPage + 1) * PROJECTS_PER_DISTRICT),
    [districtPage, rankedProjects],
  );
  visibleProjectsRef.current = visibleProjects;

  useEffect(() => {
    if (districtPage >= districtCount) setDistrictPage(districtCount - 1);
  }, [districtCount, districtPage]);

  useEffect(() => {
    const village = villageRef.current;
    if (!village) return undefined;
    const syncFullscreenState = () => setFullscreen(document.fullscreenElement === village);
    const exitFallbackFullscreen = (event: KeyboardEvent) => {
      if (event.key === "Escape" && fullscreen && document.fullscreenElement !== village) setFullscreen(false);
    };
    document.addEventListener("fullscreenchange", syncFullscreenState);
    document.addEventListener("keydown", exitFallbackFullscreen);
    return () => {
      document.removeEventListener("fullscreenchange", syncFullscreenState);
      document.removeEventListener("keydown", exitFallbackFullscreen);
    };
  }, [fullscreen]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    let resizeFrame = 0;
    const bridge: SceneBridge = {
      projects: () => visibleProjectsRef.current,
      callbacks: () => callbacksRef.current,
      debugOverlay: () => debugOverlayRef.current,
      messageFirstSeen: messageFirstSeenRef.current,
      onReady: (metrics) => {
        host.dataset.engine = "phaser-4";
        host.dataset.motionModel = "seeded-random-a-star";
        host.dataset.roamingPolicy = "available-agents-only";
        host.dataset.assetLayerModel = "flat-base-independent-transparent-sprites";
        host.dataset.occlusionStrategy = "foreground-alpha-fade";
        host.dataset.characterGrounding = "foot-aligned-shadow";
        host.dataset.navigationCellSize = String(VILLAGE_LEVEL.navigation.cellSize);
        host.dataset.navigationWalkableCellCount = String(metrics.navigationWalkableCellCount);
        host.dataset.navigationComponentCount = String(metrics.navigationComponentCount);
        host.dataset.unauthorizedRoomExitCount = String(metrics.unauthorizedRoomExitCount);
        host.dataset.textRenderer = "high-dpi-dom";
        host.dataset.gardenLayerModel = "independent-transparent-sprite";
        host.dataset.groundObjectCount = "0";
        host.dataset.roamingAgentCount = String(metrics.roamingAgentCount);
        host.dataset.actorCount = String(metrics.actorCount);
        host.dataset.collisionBodyCount = String(metrics.collisionBodyCount);
        host.dataset.foregroundObjectCount = String(metrics.foregroundObjectCount);
        host.dataset.blockedRouteCount = String(metrics.blockedRouteCount);
        host.dataset.blockedSlotCount = String(metrics.blockedSlotCount);
        host.dataset.walkDirections = String(DIRECTIONS.length);
        host.dataset.framesPerDirection = String(WALK_FRAMES_PER_DIRECTION);
        setRendererState("ready");
      },
      onNavigationSample: (destinationCount, uniqueDestinationCount) => {
        host.dataset.randomDestinationCount = String(destinationCount);
        host.dataset.uniqueDestinationCount = String(uniqueDestinationCount);
      },
      onOcclusionSample: (fadedObjectCount) => {
        host.dataset.fadedObjectCount = String(fadedObjectCount);
      },
      onFailure: () => setRendererState("failed"),
      onFrameSample: (frame, direction) => {
        host.dataset.animationFrame = frame;
        host.dataset.animationDirection = direction;
      },
    };
    const scene = new CommonsVillageScene(bridge);
    sceneRef.current = scene;
    const game = new Phaser.Game({
      type: Phaser.AUTO,
      parent: host,
      width: Math.max(320, host.clientWidth),
      height: Math.max(180, host.clientHeight),
      backgroundColor: "#102f30",
      transparent: false,
      pixelArt: true,
      roundPixels: true,
      antialias: false,
      antialiasGL: false,
      powerPreference: "low-power",
      banner: false,
      loader: { imageLoadType: "HTMLImageElement" },
      dom: { createContainer: true, pointerEvents: "none" },
      input: { mouse: true, touch: true },
      scale: { mode: Phaser.Scale.NONE },
      scene: [scene],
    });
    game.canvas.className = "agent-village__canvas";
    game.canvas.setAttribute("aria-label", "Animated Commons Agent village powered by Phaser");

    const resizeObserver = new ResizeObserver(() => {
      window.cancelAnimationFrame(resizeFrame);
      resizeFrame = window.requestAnimationFrame(() => {
        const width = Math.max(320, host.clientWidth);
        const height = Math.max(180, host.clientHeight);
        game.scale.resize(width, height);
        scene.refresh();
      });
    });
    resizeObserver.observe(host);

    return () => {
      resizeObserver.disconnect();
      window.cancelAnimationFrame(resizeFrame);
      sceneRef.current = null;
      game.destroy(true);
    };
  }, []);

  useEffect(() => {
    sceneRef.current?.refresh();
  }, [debugOverlay, visibleProjects]);

  const activeAgents = snapshot?.projects.reduce((total, project) => total + project.project.active_agent_count, 0) || 0;
  const activeProjects = snapshot?.projects.filter((project) => project.project.active_agent_count > 0).length || 0;
  const recentMessages = snapshot?.projects.reduce((total, project) => total + project.recent_messages.filter((message) => {
    const created = new Date(message.created_at).getTime();
    return Number.isFinite(created) && created >= Date.now() - RECENT_MESSAGE_WINDOW_MS;
  }).length, 0) || 0;

  function guardDistrictPointer(event: ReactPointerEvent<HTMLDivElement>): void {
    event.stopPropagation();
    if (sceneRef.current) sceneRef.current.input.enabled = false;
  }

  function releaseDistrictPointer(event: ReactPointerEvent<HTMLDivElement>): void {
    event.stopPropagation();
    window.requestAnimationFrame(() => {
      if (sceneRef.current) sceneRef.current.input.enabled = true;
    });
  }

  async function toggleFullscreen(): Promise<void> {
    const village = villageRef.current;
    if (!village) return;
    if (fullscreen) {
      if (document.fullscreenElement === village && document.exitFullscreen) await document.exitFullscreen();
      else setFullscreen(false);
      return;
    }
    try {
      if (village.requestFullscreen) await village.requestFullscreen({ navigationUI: "hide" });
      setFullscreen(true);
    } catch {
      setFullscreen(true);
    }
  }

  return (
    <section
      ref={villageRef}
      className={`agent-village${fullscreen ? " agent-village--fullscreen" : ""}`}
      aria-labelledby="agent-village-title"
      data-fullscreen={fullscreen}
      data-debug-overlay={debugOverlay}
      data-render-state={rendererState}
      data-project-count={snapshot?.projects.length || fallbackProjects.length}
      data-agent-count={activeAgents}
      data-recent-message-count={recentMessages}
      data-project-capacity={PROJECTS_PER_DISTRICT}
      data-district-page={districtPage + 1}
      data-district-count={districtCount}
      data-visible-project-count={visibleProjects.length}
    >
      <div className="agent-village__heading">
        <div>
          <span className="agent-village__eyebrow"><span /> Live coordination map</span>
          <h2 id="agent-village-title">The Commons floor</h2>
        </div>
        <div className="agent-village__heading-actions">
          <div className="agent-village__summary"><strong>{activeAgents}</strong><span>active Agents across<br />{activeProjects} busy Projects</span></div>
          {collisionDebugAvailable && (
            <button
              type="button"
              className={`agent-village__fullscreen-button${debugOverlay ? " agent-village__fullscreen-button--active" : ""}`}
              aria-label={debugOverlay ? "Hide collision overlay" : "Show collision overlay"}
              aria-pressed={debugOverlay}
              title={debugOverlay ? "Hide collision overlay" : "Show collision overlay"}
              onClick={(event) => {
                event.stopPropagation();
                setDebugOverlay((current) => !current);
              }}
            >
              <ScanLine size={16} />
            </button>
          )}
          <button
            type="button"
            className="agent-village__fullscreen-button"
            aria-label={fullscreen ? "Exit village fullscreen" : "Enter village fullscreen"}
            aria-pressed={fullscreen}
            title={fullscreen ? "Exit fullscreen" : "Open fullscreen"}
            onClick={(event) => {
              event.stopPropagation();
              void toggleFullscreen();
            }}
          >
            {fullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
        </div>
      </div>
      <div className="agent-village__stage" ref={hostRef}>
        {(loading || rendererState === "loading") && <div className="agent-village__loading"><span /><span>Opening the floor...</span></div>}
        {(error || rendererState === "failed") && (
          <div className="agent-village__fallback">
            <strong>Village view unavailable</strong>
            <span>{error || "This browser could not initialize the Phaser renderer."}</span>
          </div>
        )}
        {debugOverlay && (
          <div className="agent-village__debug-legend" aria-label="Collision overlay legend">
            <span><i className="agent-village__debug-swatch agent-village__debug-swatch--walkable" />Walkable edge</span>
            <span><i className="agent-village__debug-swatch agent-village__debug-swatch--wall" />Wall collision</span>
            <span><i className="agent-village__debug-swatch agent-village__debug-swatch--object" />Object collision</span>
            <span><i className="agent-village__debug-swatch agent-village__debug-swatch--portal" />Entrance</span>
          </div>
        )}
      </div>
      <div className="agent-village__legend">
        <span><i className="agent-village__legend-pixel agent-village__legend-pixel--busy" />Working</span>
        <span><i className="agent-village__legend-pixel agent-village__legend-pixel--idle" />Available</span>
        <span><i className="agent-village__legend-bubble" />Recent message</span>
        {districtCount > 1 && (
          <div className="agent-village__district-controls" onPointerDown={guardDistrictPointer} onPointerUp={releaseDistrictPointer} onPointerCancel={releaseDistrictPointer} onClick={(event) => event.stopPropagation()}>
            <button type="button" aria-label="Previous Project district" title="Previous Project district" disabled={districtPage === 0} onClick={() => setDistrictPage((current) => Math.max(0, current - 1))}><ChevronLeft size={13} /></button>
            <span>District {districtPage + 1} / {districtCount}</span>
            <button type="button" aria-label="Next Project district" title="Next Project district" disabled={districtPage >= districtCount - 1} onClick={() => setDistrictPage((current) => Math.min(districtCount - 1, current + 1))}><ChevronRight size={13} /></button>
          </div>
        )}
        <small className={districtCount > 1 ? "" : "agent-village__legend-help--solo"}>Click a Project station or Agent to inspect it.</small>
      </div>
      <div className="agent-village__accessible-list" aria-live="polite">
        {accessibleProjects.map((project) => (
          <p key={project.project.project_id}>{project.project.display_name}: {project.agents.length ? project.agents.map(agentName).join(", ") : "no active Agents"}</p>
        ))}
      </div>
    </section>
  );
}
