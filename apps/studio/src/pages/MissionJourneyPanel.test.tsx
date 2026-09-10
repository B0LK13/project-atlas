// @vitest-environment jsdom
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MissionJourneyPanel } from "./MissionJourneyPanel";
import type { MissionJourneyProjection } from "../types";

const journey: MissionJourneyProjection = {
  schema: "ATLAS_STUDIO_MISSION_JOURNEY_V1",
  generated_at_utc: "2026-09-10T00:00:00Z",
  repository: "owner/repo",
  mission: { mission_status: "HUMAN_ATTENTION_REQUIRED", freshness_state: "LIVE", snapshot_fingerprint: "fp", attention_count: 1 },
  knowledge: { state: "RETRIEVED", items: [{ title: "ADR 35", kind: "decision", path: "docs/adr/ADR-035.md", provenance: { source_path: "docs/adr/ADR-035.md" } }] },
  development: { candidate_identity: { top_claim_lanes: [{ lane: "pr/123", action_class: "READONLY_ANALYZE" }] }, prerequisites: [], missing_prerequisites: [] },
  next_actions: { claim_candidates: { candidates: [] }, monitoring: { command: "atlas-studio action-evidence" }, continuity: { command: "atlas-studio continuity" }, mission_session: { command: "atlas-studio session" } },
  honesty: { studio_ui_ne_authority: true, ui_state_is_projection: true, grants_no_mutation: true, attention_ne_authorization: true, stale_ne_current: true, unknown_ne_healthy: true },
  provenance: { generator: "test" },
};

afterEach(cleanup);
describe("Mission Journey contract surface", () => {
  it("shows mission, provenance, safe next-step handoffs and lane selection", () => {
    const loadTask = vi.fn();
    render(<MissionJourneyPanel journey={journey} loading={false} error={null} taskContext={null} taskLoading={false} taskError={null} onLoadTask={loadTask} />);
    expect(screen.getByText("Current mission")).toBeTruthy();
    expect(screen.getByText("ADR 35")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Development lane"), { target: { value: "pr/123" } });
    fireEvent.click(screen.getByRole("button", { name: "Inspect task context" }));
    expect(loadTask).toHaveBeenCalledWith("pr/123");
    expect(screen.getAllByText("Auto-retry: forbidden · authority: none").length).toBe(3);
    expect(screen.queryByRole("button", { name: /execute|resume/i })).toBeNull();
  });
});
