import { expect, test } from "@playwright/test";
import a1 from "../src/data/test-fixtures/generated-a1-packet.json" with { type: "json" };
import journey from "../src/data/test-fixtures/mission-journey.json" with { type: "json" };

const base = "http://127.0.0.1:47631";

test("mission workspace connects knowledge to a safe lane inspection", async ({ page }) => {
  const journeyWithLane = structuredClone(journey);
  journeyWithLane.development.candidate_identity = { top_claim_lanes: [{ lane: "pr/123", action_class: "READONLY_ANALYZE" }] };
  await page.route(`${base}/v1/mission-control`, (route) => route.fulfill({ json: a1 }));
  await page.route(`${base}/v1/mission-journey`, (route) => route.fulfill({ json: journeyWithLane }));
  await page.goto("/#/mission-control");
  await expect(page.getByRole("heading", { name: "Mission workspace" })).toBeVisible();
  await expect(page.getByText("ADR 035")).toBeVisible();
  await expect(page.getByText("These are supported external handoffs from the contract.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mission Control" })).toBeVisible();
  const lane = page.getByLabel("Development lane");
  await expect(lane).toBeVisible();
  await expect(page.getByRole("button", { name: "Inspect task context" })).toBeDisabled();
  await expect(page.getByRole("button", { name: /execute|resume/i })).toHaveCount(0);
});

test("mission journey failure stays explicit while A1 remains inspectable", async ({ page }) => {
  await page.route(`${base}/v1/mission-control`, (route) => route.fulfill({ json: a1 }));
  await page.route(`${base}/v1/mission-journey`, (route) => route.fulfill({ status: 503, json: { reason: "MISSION_JOURNEY_OFFLINE" } }));
  await page.goto("/#/mission-control");
  await expect(page.getByRole("heading", { name: "Mission workspace unavailable" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mission Control" })).toBeVisible();
  await expect(page.getByText("Mission Journey unavailable")).toBeVisible();
});

test("selected task context survives route changes and a reload", async ({ page }) => {
  const journeyWithLane = structuredClone(journey);
  journeyWithLane.development.candidate_identity = { top_claim_lanes: [{ lane: "pr/123", action_class: "READONLY_ANALYZE" }] };
  const task = {
    schema: "ATLAS_STUDIO_TASK_CONTEXT_V1", package: "AS-STUDIO-A2-003", generated_at_utc: "2026-09-10T00:00:00Z",
    repository: "B0LK13/project-atlas", agent: "generic", lane: "pr/123",
    freshness: { state: "KNOWN", reasons: [], fingerprints: {} }, attention: [],
    lane_state: { status: "KNOWN", lane: "pr/123", identity: { pr: 123, head: "abc", tree: "def", ownership: "OWNED", owner: "generic" }, owned_by_agent: true, actions: [], blockers: [], dependencies: [], stack: { status: "UNKNOWN" }, implementation_vs_main: { state: "UNKNOWN", merged: "UNKNOWN" } },
    knowledge: { state: "UNKNOWN", lenses: {}, provenance: { authority: false } },
    next_step: { status: "NO_SUPPORTED_ACTION", authorization: "NOT_GRANTED_BY_THIS_PACKET", prerequisites: [] }, recovery: [],
    continuation: { coordination_handoff: { built_here: false }, knowledge_handoff: { built_here: false }, agent_context: {}, fingerprints: {}, resume_checklist: [], fingerprint: "0000000000000000000000000000000000000000000000000000000000000000" },
    missing: [], honesty: { studio_ui_ne_authority: true, grants_no_mutation: true, attention_ne_authorization: true, stale_ne_current: true, unknown_ne_healthy: true, knowledge_ne_permission: true, next_step_ne_authorization: true, continuation_ne_execution: true, missing_shown_explicitly: true, task_context_ne_mutation: true },
    provenance: { generator: "fixture", presentation_only: true, grants_no_mutation: true, truth_sources: [] }, fingerprint: "0000000000000000000000000000000000000000000000000000000000000000",
  };
  await page.route(`${base}/v1/mission-control`, (route) => route.fulfill({ json: a1 }));
  await page.route(`${base}/v1/mission-journey`, (route) => route.fulfill({ json: journeyWithLane }));
  await page.route(`${base}/v1/task-context?lane=pr%2F123`, (route) => route.fulfill({ json: task }));
  await page.goto("/#/mission-control");
  await page.getByLabel("Development lane").selectOption("pr/123");
  await page.getByRole("button", { name: "Inspect task context" }).click();
  await expect(page.getByRole("heading", { name: "Task context · pr/123" })).toBeVisible();
  await page.goto("/#/agents");
  await expect(page.getByRole("region", { name: "Selected task context" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("region", { name: "Selected task context" })).toBeVisible();
});
