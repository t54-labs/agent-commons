import { expect, test, type Page } from "@playwright/test";


async function signIn(page: Page, path = "/app/") {
  await page.goto(path);
  await expect(page.getByRole("heading", { name: "See how your agents work together." })).toBeVisible();
  await page.getByLabel("Team access token").fill("console-e2e-token");
  await page.getByRole("button", { name: "Open Console" }).click();
  await expect(page.getByRole("heading", { name: "The Commons floor" })).toBeVisible();
}

function projectCard(page: Page, name: string) {
  return page.locator(".project-card").filter({ hasText: name });
}

test("operator starts from a clickable Workspace overview and switches Projects", async ({ page }, testInfo) => {
  await signIn(page);

  await expect(page.getByText("T54 Agent Workspace")).toHaveCount(0);
  await expect(projectCard(page, "Commons Team")).toBeVisible();
  await expect(projectCard(page, "Platform Api")).toBeVisible();
  await expect(page.locator(".metric--teal").getByText("4 / 60", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Active / registered: Current / known Agents" })).toBeVisible();
  await expect(page.getByText("Online / active", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Relay connected")).toHaveCount(0);
  await expect(page.getByText("Live", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Show collision overlay" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Hide collision overlay" })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.length)).toBe(0);

  await page.getByRole("button", { name: "Blocked: Needs coordination" }).click();
  await expect(page.locator(".project-card")).toHaveCount(1);
  await expect(projectCard(page, "Commons Team")).toBeVisible();

  await page.getByRole("button", { name: "Projects: All Relay projects" }).click();
  await expect(page.locator(".project-card")).toHaveCount(2);
  await projectCard(page, "Platform Api").click();
  await expect(page.getByRole("heading", { name: "Platform Api" })).toBeVisible();
  await expect(page.getByText("Validate the staging API", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "All projects" }).click();
  await expect(page.getByRole("heading", { name: "The Commons floor" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("workspace-overview.png"), fullPage: true });
});

test("Workspace directory switches between People, Agents, and Projects", async ({ page }) => {
  await signIn(page);

  await page.getByRole("button", { name: "Directory" }).click();
  await expect(page.getByLabel("Directory summary")).toBeVisible();
  await expect(page.getByRole("heading", { name: "People", exact: true })).toBeVisible();
  await expect(page.getByText("Sergio", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("@sergio-*", { exact: true })).toBeVisible();

  const directoryTabs = page.getByRole("group", { name: "Directory view" });
  await directoryTabs.getByRole("button", { name: "Agents", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Agents", exact: true })).toBeVisible();
  const consoleAgent = page.locator(".directory-table tbody tr").filter({ hasText: "@sergio-codex-console" });
  await expect(consoleAgent).toContainText("Sergio");
  await expect(consoleAgent).toContainText("Commons Team");

  await directoryTabs.getByRole("button", { name: "Projects", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();
  const commonsProject = page.locator(".directory-table tbody tr").filter({ hasText: "Commons Team" });
  const projectCounts = commonsProject.locator(".directory-cell--count");
  await expect(projectCounts.nth(0)).toContainText("3 / 4");
  await expect(projectCounts.nth(1)).toContainText("1 blocked");
  const taskCountText = await projectCounts.nth(1).textContent();
  const taskCounts = taskCountText?.match(/(\d+)\s*\/\s*(\d+)/);
  expect(taskCounts).not.toBeNull();
  expect(Number(taskCounts![1])).toBeLessThanOrEqual(Number(taskCounts![2]));

  await page.getByLabel("Search directory").fill("platform");
  await expect(page.locator(".directory-table tbody tr")).toHaveCount(1);
  await expect(page.locator(".directory-table tbody tr")).toContainText("Platform Api");
});

test.describe("UTC activity calendar", () => {
  test.use({ timezoneId: "Pacific/Kiritimati" });

  test("keeps Relay dates in UTC and loads a complete day through cursors", async ({ page }) => {
    const utcDate = new Date().toISOString().slice(0, 10);
    const utcLabel = new Intl.DateTimeFormat("en", {
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    }).format(new Date(`${utcDate}T12:00:00Z`));
    const requestedCursors: Array<string | null> = [];

    await page.route("**/v1/console/day?**", async (route) => {
      const url = new URL(route.request().url());
      const before = url.searchParams.get("before");
      requestedCursors.push(before);
      const older = Boolean(before);
      const events = older
        ? [{
            event_id: 40,
            project_id: "commons-team",
            event_type: "message.sent",
            actor_agent_id: "agent_claude_docs",
            actor_handle: "sergio-claude-docs",
            actor_runtime: "claude-code",
            project_display_name: "Commons Team",
            payload: { body: "Older documentation status" },
            created_at: `${utcDate}T08:00:00Z`,
          }]
        : [
            {
              event_id: 42,
              project_id: "commons-team",
              event_type: "message.sent",
              actor_agent_id: "agent_codex_console",
              actor_handle: "sergio-codex-console",
              actor_runtime: "codex",
              project_display_name: "Commons Team",
              payload: { body: "Current Console status" },
              created_at: `${utcDate}T18:00:00Z`,
            },
            {
              event_id: 41,
              project_id: "platform-api",
              event_type: "message.sent",
              actor_agent_id: "agent_codex_platform",
              actor_handle: "sergio-codex-platform",
              actor_runtime: "codex",
              project_display_name: "Platform Api",
              payload: { body: "Current API status" },
              created_at: `${utcDate}T12:00:00Z`,
            },
          ];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          date: utcDate,
          project_id: null,
          totals: { total: 3, tasks: 0, messages: 3, leases: 0, agents: 0, other: 0 },
          events,
          page: {
            limit: 200,
            returned_count: events.length,
            has_more: !older,
            next_cursor: older ? null : "41",
            window_complete: older,
          },
        }),
      });
    });

    await signIn(page);
    await expect(page.getByText(/UTC$/, { exact: false }).first()).toBeVisible();
    await page.getByRole("button", { name: `Show activity for ${utcLabel}` }).click();

    const dayRail = page.getByLabel(new RegExp(`Coordination activity on .*${utcLabel}`));
    await expect(dayRail).toBeVisible();
    await expect(dayRail.getByLabel("Messages events").locator(".day-summary__event")).toHaveCount(2);
    await expect(dayRail.getByText("Showing 2 of 3 events", { exact: true })).toBeVisible();
    await dayRail.getByRole("button", { name: "Load older" }).click();
    await expect(dayRail.getByLabel("Messages events").locator(".day-summary__event")).toHaveCount(3);
    await expect(dayRail.getByText("Showing 2 of 3 events", { exact: true })).toHaveCount(0);
    expect(requestedCursors).toEqual([null, "41"]);
  });
});

test("Workspace overview renders a live interactive Phaser Agent village", async ({ page }, testInfo) => {
  await signIn(page);

  const village = page.locator(".agent-village");
  await expect(village.getByRole("heading", { name: "The Commons floor" })).toBeVisible();
  await expect(village).toHaveAttribute("data-render-state", "ready", { timeout: 12_000 });
  await expect(village).toHaveAttribute("data-project-count", "2");
  await expect(village).toHaveAttribute("data-agent-count", "4");
  await expect(village.locator("canvas")).toBeVisible();
  const stage = village.locator(".agent-village__stage");
  await expect(stage).toHaveAttribute("data-engine", "phaser-4");
  await expect(stage).toHaveAttribute("data-motion-model", "seeded-random-a-star");
  await expect(stage).toHaveAttribute("data-roaming-policy", "available-agents-only");
  await expect(stage).toHaveAttribute("data-asset-layer-model", "flat-base-independent-transparent-sprites");
  await expect(stage).toHaveAttribute("data-occlusion-strategy", "foreground-alpha-fade");
  await expect(stage).toHaveAttribute("data-character-grounding", "foot-aligned-shadow");
  await expect(stage).toHaveAttribute("data-navigation-cell-size", "16");
  await expect(stage).toHaveAttribute("data-navigation-walkable-cell-count", /^(?:[1-9]\d{3,})$/);
  await expect(stage).toHaveAttribute("data-navigation-component-count", "1");
  await expect(stage).toHaveAttribute("data-unauthorized-room-exit-count", "0");
  await expect(stage).toHaveAttribute("data-text-renderer", "high-dpi-dom");
  await expect(stage).toHaveAttribute("data-garden-layer-model", "independent-transparent-sprite");
  await expect(stage).toHaveAttribute("data-ground-object-count", "0");
  await expect(stage).toHaveAttribute("data-roaming-agent-count", "1");
  await expect(stage).toHaveAttribute("data-collision-body-count", "51");
  await expect(stage).toHaveAttribute("data-foreground-object-count", "16");
  await expect(stage).toHaveAttribute("data-faded-object-count", /^\d+$/);
  await expect(stage).toHaveAttribute("data-blocked-route-count", "0");
  await expect(stage).toHaveAttribute("data-blocked-slot-count", "0");
  await expect(stage).toHaveAttribute("data-walk-directions", "4");
  await expect(stage).toHaveAttribute("data-frames-per-direction", "4");
  await expect.poll(() => stage.getAttribute("data-animation-frame"), { timeout: 6_000 }).not.toBeNull();
  const initialAnimationFrame = await stage.getAttribute("data-animation-frame");
  await expect.poll(() => stage.getAttribute("data-animation-frame"), { timeout: 3_000 }).not.toBe(initialAnimationFrame);
  await expect(stage).toHaveAttribute("data-animation-direction", /^(down|left|right|up)$/);
  await expect(stage).toHaveAttribute("data-random-destination-count", /^[1-9]\d*$/);
  await expect(stage).toHaveAttribute("data-unique-destination-count", /^[1-9]\d*$/);

  const projectSigns = village.locator(".village-project-sign");
  const agentNames = village.locator(".village-agent-ui__name");
  const messageBubbles = village.locator(".village-agent-ui__bubble");
  await expect(projectSigns).toHaveCount(2);
  await expect(agentNames).toHaveCount(4);
  const initialMessageBubbleCount = await messageBubbles.count();
  expect(initialMessageBubbleCount).toBeGreaterThan(0);
  const textSizes = await page.evaluate(() => ({
    project: parseFloat(getComputedStyle(document.querySelector(".village-project-sign strong")!).fontSize),
    agent: parseFloat(getComputedStyle(document.querySelector(".village-agent-ui__name")!).fontSize),
    bubble: parseFloat(getComputedStyle(document.querySelector(".village-agent-ui__bubble")!).fontSize),
    agentDisplay: getComputedStyle(document.querySelector(".village-agent-ui__name")!).display,
    bubbleDisplay: getComputedStyle(document.querySelector(".village-agent-ui__bubble")!).display,
  }));
  const mobile = testInfo.project.name === "mobile";
  expect(textSizes.project).toBeGreaterThanOrEqual(mobile ? 8.5 : 10);
  expect(textSizes.agent).toBeGreaterThanOrEqual(mobile ? 7.5 : 9);
  expect(textSizes.bubble).toBeGreaterThanOrEqual(mobile ? 8.5 : 10);
  expect(textSizes.agentDisplay).toBe(mobile ? "none" : "block");
  expect(textSizes.bubbleDisplay).toBe(mobile ? "none" : "block");

  if (mobile) {
    const signBoxes = await projectSigns.evaluateAll((elements) => elements.map((element) => {
      const bounds = element.getBoundingClientRect();
      return { left: bounds.left, right: bounds.right };
    }));
    expect(signBoxes[0].right).toBeLessThanOrEqual(signBoxes[1].left);
  }

  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(projectSigns).toHaveCount(2);
  await expect(agentNames).toHaveCount(4);
  await expect(messageBubbles).toHaveCount(initialMessageBubbleCount);

  const canvasImage = await village.screenshot({ path: testInfo.outputPath("agent-village.png") });
  expect(canvasImage.byteLength).toBeGreaterThan(20_000);
  await page.waitForTimeout(1_600);
  const animatedFrame = await village.locator("canvas").screenshot();
  expect(Buffer.compare(canvasImage, animatedFrame)).not.toBe(0);

  const canvas = village.locator("canvas");
  const bounds = await canvas.boundingBox();
  expect(bounds).not.toBeNull();
  await canvas.click({ position: { x: bounds!.width * 0.23, y: bounds!.height * 0.285 } });
  await expect(page.getByRole("heading", { name: "Commons Team" })).toBeVisible();
});

test("Agent hover profiles expose owner and registration device without opening the drawer", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers the pointer hover profile");
  await signIn(page);

  const village = page.locator(".agent-village");
  await expect(village).toHaveAttribute("data-render-state", "ready", { timeout: 12_000 });
  const actor = village.locator('.village-agent-ui[data-agent-id="agent_codex_console"]');
  const hoverTarget = actor.getByRole("button", { name: "Preview @sergio-codex-console" });
  const profile = actor.locator(".village-agent-ui__profile");

  await hoverTarget.hover();
  await expect(profile).toHaveAttribute("aria-hidden", "false");
  await expect(profile).toContainText("@sergio-codex-console");
  await expect(profile).toContainText("Sergio");
  await expect(profile).toContainText("sergio-mac-studio");
  await expect(profile).toContainText("Codex");
  await expect(profile).toContainText("commons");
  await expect(page.locator(".agent-drawer")).toHaveCount(0);

  const stageBounds = await village.locator(".agent-village__stage").boundingBox();
  const profileBounds = await profile.boundingBox();
  expect(stageBounds).not.toBeNull();
  expect(profileBounds).not.toBeNull();
  expect(profileBounds!.x).toBeGreaterThanOrEqual(stageBounds!.x);
  expect(profileBounds!.x + profileBounds!.width).toBeLessThanOrEqual(stageBounds!.x + stageBounds!.width);
  expect(profileBounds!.y).toBeGreaterThanOrEqual(stageBounds!.y);
  expect(profileBounds!.y + profileBounds!.height).toBeLessThanOrEqual(stageBounds!.y + stageBounds!.height);
  await page.screenshot({ path: testInfo.outputPath("agent-hover-profile.png") });

  await page.mouse.move(stageBounds!.x + stageBounds!.width - 2, stageBounds!.y + stageBounds!.height - 2);
  await expect(profile).toHaveAttribute("aria-hidden", "true");

  await hoverTarget.click();
  await expect(page.locator(".agent-drawer").getByRole("heading", { name: "@sergio-codex-console" })).toBeVisible();
});

test("Village fullscreen control fills the browser viewport and restores cleanly", async ({ page }, testInfo) => {
  await signIn(page);

  const village = page.locator(".agent-village");
  await expect(village).toHaveAttribute("data-render-state", "ready", { timeout: 12_000 });
  const initialBounds = await village.boundingBox();
  expect(initialBounds).not.toBeNull();

  await page.evaluate(() => {
    let fullscreenElement: Element | null = null;
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => fullscreenElement,
    });
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: async function requestFullscreen(this: HTMLElement) {
        fullscreenElement = this;
        document.dispatchEvent(new Event("fullscreenchange"));
      },
    });
    Object.defineProperty(document, "exitFullscreen", {
      configurable: true,
      value: async () => {
        fullscreenElement = null;
        document.dispatchEvent(new Event("fullscreenchange"));
      },
    });
  });

  await page.getByRole("button", { name: "Enter village fullscreen" }).click();
  await expect(village).toHaveAttribute("data-fullscreen", "true");
  await expect(page.getByRole("button", { name: "Exit village fullscreen" })).toHaveAttribute("aria-pressed", "true");
  const fullscreenBounds = await village.boundingBox();
  const viewport = page.viewportSize();
  expect(fullscreenBounds).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(fullscreenBounds!.x).toBeLessThanOrEqual(1);
  expect(fullscreenBounds!.y).toBeLessThanOrEqual(1);
  expect(fullscreenBounds!.width).toBeGreaterThanOrEqual(viewport!.width - 1);
  expect(fullscreenBounds!.height).toBeGreaterThanOrEqual(viewport!.height - 1);
  expect(fullscreenBounds!.height).toBeGreaterThan(initialBounds!.height);
  await page.screenshot({ path: testInfo.outputPath("agent-village-fullscreen.png") });

  await page.getByRole("button", { name: "Exit village fullscreen" }).click();
  await expect(village).toHaveAttribute("data-fullscreen", "false");
  await expect(page.getByRole("button", { name: "Enter village fullscreen" })).toHaveAttribute("aria-pressed", "false");
});

test("Village collision overlay exposes walls, objects, walkable edges, and entrances", async ({ page }) => {
  await signIn(page, "/app/?collisionDebug=1");

  const village = page.locator(".agent-village");
  await expect(village).toHaveAttribute("data-render-state", "ready", { timeout: 12_000 });
  await expect(village).toHaveAttribute("data-debug-overlay", "true");
  await expect(page.getByLabel("Collision overlay legend")).toContainText("Wall collision");

  await page.getByRole("button", { name: "Hide collision overlay" }).click();
  await expect(village).toHaveAttribute("data-debug-overlay", "false");
  await expect(page.getByLabel("Collision overlay legend")).toHaveCount(0);

  await page.getByRole("button", { name: "Show collision overlay" }).click();
  await expect(village).toHaveAttribute("data-debug-overlay", "true");
  await expect(page.getByLabel("Collision overlay legend")).toContainText("Entrance");
});

test("Project districts make every Project reachable beyond the six-room capacity", async ({ page }) => {
  let includeOverflow = true;
  await page.route("**/v1/console/village", async (route) => {
    const response = await route.fetch();
    const snapshot = await response.json();
    const template = snapshot.projects[0];
    const overflowProjects = Array.from({ length: 6 }, (_, index) => ({
      ...template,
      project: {
        ...template.project,
        project_id: `overflow-${index + 1}`,
        display_name: `Overflow ${index + 1}`,
        active_agent_count: index % 2,
        registered_agent_count: index % 2,
        last_activity_at: new Date(Date.now() - (index + 5) * 60_000).toISOString(),
      },
      agents: [],
      recent_messages: [],
      has_more_agents: false,
    }));
    await route.fulfill({ response, json: { ...snapshot, projects: includeOverflow ? [...snapshot.projects, ...overflowProjects] : snapshot.projects } });
  });
  await signIn(page);

  const village = page.locator(".agent-village");
  const signs = village.locator(".village-project-sign");
  await expect(village).toHaveAttribute("data-project-count", "8");
  await expect(village).toHaveAttribute("data-project-capacity", "6");
  await expect(village).toHaveAttribute("data-district-count", "2");
  await expect(village).toHaveAttribute("data-district-page", "1");
  await expect(village).toHaveAttribute("data-visible-project-count", "6");
  await expect(signs).toHaveCount(6);
  const signBounds = await signs.evaluateAll((elements) => elements.map((element) => {
    const bounds = element.getBoundingClientRect();
    return { left: bounds.left, right: bounds.right, top: bounds.top, bottom: bounds.bottom };
  }));
  const overlappingSigns = signBounds.some((left, leftIndex) => signBounds.some((right, rightIndex) => (
    rightIndex > leftIndex
    && left.left < right.right
    && left.right > right.left
    && left.top < right.bottom
    && left.bottom > right.top
  )));
  expect(overlappingSigns).toBe(false);
  const firstDistrict = new Set(await signs.locator("strong").allTextContents());

  await page.getByRole("button", { name: "Next Project district" }).click();
  await expect(village).toHaveAttribute("data-district-page", "2");
  await expect(village).toHaveAttribute("data-visible-project-count", "2");
  await expect(signs).toHaveCount(2);
  const secondDistrict = new Set(await signs.locator("strong").allTextContents());
  expect([...secondDistrict].some((name) => firstDistrict.has(name))).toBe(false);
  await expect(page.getByRole("button", { name: "Next Project district" })).toBeDisabled();

  includeOverflow = false;
  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(village).toHaveAttribute("data-district-page", "1");
  await expect(village).toHaveAttribute("data-district-count", "1");
  await expect(village).toHaveAttribute("data-visible-project-count", "2");
  await expect(signs).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Next Project district" })).toHaveCount(0);
});

test("an available Agent completes multiple random destinations at runtime", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers the longer live-motion observation");
  await signIn(page);
  const stage = page.locator(".agent-village__stage");
  await expect(stage).toHaveAttribute("data-motion-model", "seeded-random-a-star", { timeout: 12_000 });
  const initialDestinationCount = Number(await stage.getAttribute("data-random-destination-count"));
  expect(initialDestinationCount).toBeGreaterThan(0);
  await expect.poll(async () => Number(await stage.getAttribute("data-random-destination-count")), { timeout: 20_000 })
    .toBeGreaterThan(initialDestinationCount);
  await expect.poll(async () => Number(await stage.getAttribute("data-unique-destination-count")), { timeout: 2_000 })
    .toBeGreaterThan(1);
});

test("independent foreground sprites fade instead of hiding Agents", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers foreground occlusion behavior");
  let crowded = true;
  await page.route("**/v1/console/village", async (route) => {
    const response = await route.fetch();
    const snapshot = await response.json();
    const project = snapshot.projects[0];
    const template = project.agents[0];
    const agents = crowded
      ? Array.from({ length: 8 }, (_, index) => ({
          ...template,
          agent_id: `occlusion-agent-${index + 1}`,
          handle: `occlusion-agent-${index + 1}`,
          status: "busy",
          presence: "online",
        }))
      : [template];
    await route.fulfill({
      response,
      json: {
        ...snapshot,
        projects: [
          {
            ...project,
            project: {
              ...project.project,
              active_agent_count: agents.length,
              registered_agent_count: agents.length,
            },
            agents,
          },
          ...snapshot.projects.slice(1),
        ],
      },
    });
  });
  await signIn(page);

  const stage = page.locator(".agent-village__stage");
  await expect(stage).toHaveAttribute("data-asset-layer-model", "flat-base-independent-transparent-sprites", { timeout: 12_000 });
  await expect(stage).toHaveAttribute("data-occlusion-strategy", "foreground-alpha-fade");
  await expect(stage).toHaveAttribute("data-faded-object-count", /^[1-9]\d*$/);

  crowded = false;
  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(stage).toHaveAttribute("data-faded-object-count", "0");
});

test("Project broadcasts and Agent direct messages stay in separate views", async ({ page }, testInfo) => {
  await signIn(page);
  await projectCard(page, "Commons Team").click();

  const projectSummary = page.getByLabel("Project summary", { exact: true });
  await expect(projectSummary.locator(".metric")).toHaveCount(4);
  await expect(projectSummary.getByRole("button", { name: "Active / registered: Current / known Agents" })).toHaveCount(0);
  await expect(page.locator(".page-heading p")).toHaveCount(0);
  await expect(page.locator(".coordination-image__agent-summary strong")).toHaveText("3 / 4");
  await expect(page.locator("#active-agents-title")).toHaveText("Active agents");
  await expect(page.locator(".agent-card").filter({ hasText: "@sergio-codex-review" })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("project-overview.png"), fullPage: true });

  await page.getByRole("button", { name: "Broadcasts: Project-wide" }).click();
  await expect(page.getByRole("heading", { name: "Broadcasts" })).toBeVisible();
  await expect(page.getByText(/PLAN \[task_/)).toBeVisible();
  await expect(page.getByText("The session-cookie boundary looks sound. Please verify SSE reconnect before rollout.")).toHaveCount(0);

  await page.getByRole("button", { name: "Agents", exact: true }).click();
  const consoleAgent = page.locator(".directory-row").filter({ hasText: "@sergio-codex-console" });
  await expect(consoleAgent).toBeVisible();
  await expect(consoleAgent.getByText("Active", { exact: true })).toBeVisible();
  await consoleAgent.click();

  const agentDrawer = page.locator(".agent-drawer");
  await expect(agentDrawer.getByRole("heading", { name: "@sergio-codex-console" })).toBeVisible();
  await expect(agentDrawer.getByRole("heading", { name: "Direct messages" })).toBeVisible();
  const directMessage = agentDrawer.getByRole("button").filter({ hasText: "The session-cookie boundary looks sound." });
  await expect(directMessage).toBeVisible();
  await expect(agentDrawer.getByText(/PLAN \[task_/)).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("agent-direct-messages.png"), fullPage: true });
  await directMessage.click();

  const messageDrawer = page.locator(".message-drawer");
  await expect(messageDrawer.getByText("Direct message", { exact: true })).toBeVisible();
  await expect(messageDrawer.getByText("@sergio-claude-relay", { exact: true })).toBeVisible();
  await expect(messageDrawer.getByText("@sergio-codex-console", { exact: true })).toBeVisible();
});

test("Project metric descriptions appear on hover without resizing the cards", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers hover behavior");
  await signIn(page);
  await projectCard(page, "Commons Team").click();

  const metric = page.getByLabel("Project summary", { exact: true }).locator(".metric").first();
  const detail = metric.locator(".metric__detail-copy");
  await expect(detail).toHaveCSS("opacity", "0");
  const boxBefore = await metric.boundingBox();
  await metric.hover();
  await expect(detail).toHaveCSS("opacity", "1");
  const boxAfter = await metric.boundingBox();
  expect(boxAfter?.width).toBe(boxBefore?.width);
  expect(boxAfter?.height).toBe(boxBefore?.height);
});

test("timeline opens Agent details outside the bounded summary preview", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers the bounded-summary fallback");
  await signIn(page);
  await projectCard(page, "Commons Team").click();

  const archivedAgentEvent = page
    .locator(".timeline-event__card")
    .filter({ hasText: "@sergio-codex-review" })
    .filter({ hasText: "Joined this project" });
  await expect(archivedAgentEvent).toBeVisible();
  await archivedAgentEvent.click();

  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
  await expect(page.locator(".agent-drawer").getByRole("heading", { name: "@sergio-codex-review" })).toBeVisible();
});

test("Project activity spans the full Console height without an inner viewport", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers the three-column Console layout");
  await signIn(page);
  await projectCard(page, "Commons Team").click();
  await expect(page.getByLabel("Project activity timeline")).toBeVisible();
  await expect(page.locator('[aria-label="Project activity timeline"] .timeline-event')).not.toHaveCount(0);

  const layout = await page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>(".console-shell");
    const rail = document.querySelector<HTMLElement>('[aria-label="Project activity timeline"]');
    const timeline = rail?.querySelector<HTMLElement>(".timeline");
    const events = timeline?.querySelectorAll<HTMLElement>(".timeline-event");
    const lastEvent = events?.item((events?.length || 0) - 1);
    if (!shell || !rail || !timeline || !lastEvent) throw new Error("Project activity layout is incomplete");
    const shellRect = shell.getBoundingClientRect();
    const railRect = rail.getBoundingClientRect();
    const lastEventRect = lastEvent.getBoundingClientRect();
    const timelineStyle = getComputedStyle(timeline);
    return {
      shellBottom: shellRect.bottom,
      railBottom: railRect.bottom,
      lastEventBottom: lastEventRect.bottom,
      timelineMaxHeight: timelineStyle.maxHeight,
      timelineOverflowY: timelineStyle.overflowY,
    };
  });

  expect(Math.abs(layout.shellBottom - layout.railBottom)).toBeLessThanOrEqual(1);
  expect(layout.timelineMaxHeight).toBe("none");
  expect(layout.timelineOverflowY).toBe("visible");
  expect(layout.lastEventBottom).toBeLessThanOrEqual(layout.railBottom + 1);
  await page.screenshot({ path: testInfo.outputPath("project-activity-full-height.png"), fullPage: true });
});

test("clickable Project overview cards lead to their detailed views", async ({ page }) => {
  await signIn(page);
  await projectCard(page, "Commons Team").click();

  await page.locator(".coordination-image").click();
  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
  await page.getByRole("button", { name: "Overview", exact: true }).click();

  const broadcast = page.locator(".broadcast-preview").first();
  await expect(broadcast).toBeVisible();
  await broadcast.click();
  await expect(page.locator(".message-drawer").getByText("Project broadcast", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close message details" }).click();

  await page.getByRole("button", { name: "Active tasks: Current work" }).click();
  await expect(page.getByRole("heading", { name: "Tasks" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Active", exact: true })).toHaveAttribute("aria-pressed", "true");
});

test("Project summary loads before paginated tab data", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers the collection request contract");
  const projectRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.includes("/v1/console/projects/platform-api")) projectRequests.push(`${url.pathname}${url.search}`);
  });

  await signIn(page);
  await projectCard(page, "Platform Api").click();
  await expect(page.getByText("Validate the staging API", { exact: true })).toBeVisible();
  expect(projectRequests.some((path) => path === "/v1/console/projects/platform-api/summary")).toBeTruthy();
  expect(projectRequests.some((path) => path === "/v1/console/projects/platform-api")).toBeFalsy();
  expect(projectRequests.some((path) => path.includes("/agents?"))).toBeFalsy();

  await page.getByRole("button", { name: "Agents", exact: true }).click();
  await expect(page.locator(".directory-row")).toHaveCount(1);
  await page.getByRole("button", { name: "All", exact: true }).click();
  await expect(page.locator(".directory-row")).toHaveCount(50);
  await expect(page.getByText("Page 1 · 50 shown", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page.locator(".directory-row")).toHaveCount(6);
  await expect(page.getByText("Page 2 · 6 shown", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Previous page" })).toBeEnabled();
});

test("Project switching hides the previous Project while the next response is pending", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers the request timing contract");
  await signIn(page);
  await projectCard(page, "Commons Team").click();
  await expect(page.locator(".coordination-image__agent-summary strong")).toHaveText("3 / 4");

  let delayedSummary = false;
  await page.route("**/v1/console/projects/platform-api/summary", async (route) => {
    if (delayedSummary) {
      await route.continue();
      return;
    }
    delayedSummary = true;
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 750));
    await route.fulfill({ response });
  });

  await page.getByRole("button", { name: "Platform Api", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Platform Api" })).toBeVisible();
  await expect(page.getByLabel("Loading project summary")).toBeVisible();
  await expect(page.getByLabel("Loading project activity")).toBeVisible();
  await expect(page.getByLabel("Project summary", { exact: true })).toHaveCount(0);
  await expect(page.getByText("3 / 4", { exact: true })).toHaveCount(0);

  await expect(page.locator(".coordination-image__agent-summary strong")).toHaveText("1 / 56");
  await expect(page.getByText("Validate the staging API", { exact: true })).toBeVisible();
});

test("a late Project response cannot overwrite a newer selection", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers the request timing contract");
  await signIn(page);
  await projectCard(page, "Commons Team").click();
  await expect(page.locator(".coordination-image__agent-summary strong")).toHaveText("3 / 4");

  let releasePlatformResponse: (() => void) | undefined;
  const platformResponseGate = new Promise<void>((resolve) => { releasePlatformResponse = resolve; });
  let heldSummary = false;
  await page.route("**/v1/console/projects/platform-api/summary", async (route) => {
    if (heldSummary) {
      await route.continue();
      return;
    }
    heldSummary = true;
    const response = await route.fetch();
    await platformResponseGate;
    await route.fulfill({ response });
  });

  await page.getByRole("button", { name: "Platform Api", exact: true }).click();
  await expect(page.getByLabel("Loading project summary")).toBeVisible();
  await page.getByRole("button", { name: "Commons Team", exact: true }).click();
  await expect(page.locator(".coordination-image__agent-summary strong")).toHaveText("3 / 4");

  releasePlatformResponse?.();
  await page.waitForTimeout(300);
  await expect(page.getByRole("heading", { name: "Commons Team" })).toBeVisible();
  await expect(page.locator(".coordination-image__agent-summary strong")).toHaveText("3 / 4");
  await expect(page.getByText("Validate the staging API", { exact: true })).toHaveCount(0);
});

test("new Relay activity reaches the timeline through SSE and is actionable", async ({ page, request }) => {
  await signIn(page);
  await projectCard(page, "Commons Team").click();
  const response = await request.post("http://127.0.0.1:8766/v1/tasks", {
    headers: {
      Authorization: "Bearer relay-e2e-token",
      "X-Commons-Project": "commons-team",
    },
    data: {
      title: "Live SSE verification",
      owner_agent_id: "agent_codex_console",
      status: "in_progress",
      current_step: "Observe the Console timeline",
      next_step: "Complete the E2E run",
      progress_percent: 10,
    },
  });
  expect(response.ok()).toBeTruthy();
  const event = page.locator(".timeline-event__card").filter({ hasText: "Started Live SSE verification" });
  await expect(event).toBeVisible({ timeout: 10_000 });
  await event.click();
  await expect(page.getByRole("heading", { name: "Tasks" })).toBeVisible();
});

test("mobile layout keeps Workspace and Project navigation readable", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "Mobile-only visual assertion");
  await signIn(page);
  await expect(page.getByRole("button", { name: "All projects" })).toBeVisible();
  await expect(projectCard(page, "Commons Team")).toBeVisible();
  await expect(page.locator(".agent-village")).toHaveAttribute("data-render-state", "ready", { timeout: 12_000 });
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
  await page.screenshot({ path: testInfo.outputPath("workspace-mobile.png"), fullPage: true });
});
