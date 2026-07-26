import { expect, test, type Page } from "@playwright/test";


async function signIn(page: Page) {
  await page.goto("/app/");
  await expect(page.getByRole("heading", { name: "See how your agents work together." })).toBeVisible();
  await page.getByLabel("Team access token").fill("console-e2e-token");
  await page.getByRole("button", { name: "Open Console" }).click();
  await expect(page.getByRole("heading", { name: "Workspace overview" })).toBeVisible();
}

function projectCard(page: Page, name: string) {
  return page.locator(".project-card").filter({ hasText: name });
}

test("operator starts from a clickable Workspace overview and switches Projects", async ({ page }, testInfo) => {
  await signIn(page);

  await expect(page.getByText("T54 Agent Workspace")).toBeVisible();
  await expect(projectCard(page, "Commons Team")).toBeVisible();
  await expect(projectCard(page, "Platform Api")).toBeVisible();
  await expect(page.locator(".metric--teal").getByText("4 / 60", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Active / registered: Current / known Agents" })).toBeVisible();
  await expect(page.getByText("Online / active", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Relay connected")).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "Workspace overview" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("workspace-overview.png"), fullPage: true });
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
  await expect(page.locator(".agent-card").filter({ hasText: "@codex-review" })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("project-overview.png"), fullPage: true });

  await page.getByRole("button", { name: "Broadcasts: Project-wide" }).click();
  await expect(page.getByRole("heading", { name: "Broadcasts" })).toBeVisible();
  await expect(page.getByText(/PLAN \[task_/)).toBeVisible();
  await expect(page.getByText("The session-cookie boundary looks sound. Please verify SSE reconnect before rollout.")).toHaveCount(0);

  await page.getByRole("button", { name: "Agents", exact: true }).click();
  const consoleAgent = page.locator(".directory-row").filter({ hasText: "@codex-console" });
  await expect(consoleAgent).toBeVisible();
  await expect(consoleAgent.getByText("Active", { exact: true })).toBeVisible();
  await consoleAgent.click();

  const agentDrawer = page.locator(".agent-drawer");
  await expect(agentDrawer.getByRole("heading", { name: "@codex-console" })).toBeVisible();
  await expect(agentDrawer.getByRole("heading", { name: "Direct messages" })).toBeVisible();
  const directMessage = agentDrawer.getByRole("button").filter({ hasText: "The session-cookie boundary looks sound." });
  await expect(directMessage).toBeVisible();
  await expect(agentDrawer.getByText(/PLAN \[task_/)).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("agent-direct-messages.png"), fullPage: true });
  await directMessage.click();

  const messageDrawer = page.locator(".message-drawer");
  await expect(messageDrawer.getByText("Direct message", { exact: true })).toBeVisible();
  await expect(messageDrawer.getByText("@claude-relay", { exact: true })).toBeVisible();
  await expect(messageDrawer.getByText("@codex-console", { exact: true })).toBeVisible();
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

  const archivedAgentEvent = page.locator(".timeline-event__card").filter({ hasText: "@codex-review" }).filter({ hasText: "Joined this project" });
  await expect(archivedAgentEvent).toBeVisible();
  await archivedAgentEvent.click();

  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
  await expect(page.locator(".agent-drawer").getByRole("heading", { name: "@codex-review" })).toBeVisible();
});

test("Project activity spans the full Console height without an inner viewport", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Desktop covers the three-column Console layout");
  await signIn(page);
  await projectCard(page, "Commons Team").click();

  const layout = await page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>(".console-shell");
    const rail = document.querySelector<HTMLElement>('[aria-label="Project activity timeline"]');
    const timeline = rail?.querySelector<HTMLElement>(".timeline");
    const lastEvent = timeline?.querySelector<HTMLElement>(".timeline-event:last-of-type");
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
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
  await page.screenshot({ path: testInfo.outputPath("workspace-mobile.png"), fullPage: true });
});
