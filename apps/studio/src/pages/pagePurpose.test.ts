import { describe, expect, it } from "vitest";
import { pagePurpose, secondaryAttentionLabel, viewLabel } from "./pagePurpose";

describe("page purpose", () => {
  it("gives each operational route a distinct question", () => {
    expect(pagePurpose("agents").question).toContain("agents");
    expect(pagePurpose("work-graph").question).toContain("dependencies");
    expect(pagePurpose("repository").question).toContain("repository");
    expect(pagePurpose("verification").question).toContain("evidence");
    expect(pagePurpose("knowledge").question).toContain("knowledge");
    expect(pagePurpose("chronicle").question).toContain("happened");
  });

  it("makes the secondary attention affordance compact and count-precise", () => {
    expect(secondaryAttentionLabel(118)).toBe("118 attention items · open Mission Control");
    expect(secondaryAttentionLabel(0)).toBe("No attention items supplied · open Mission Control");
  });

  it("uses deliberate names for source views", () => {
    expect(viewLabel("agents", "agents_lanes")).toBe("Observed agent directory");
    expect(viewLabel("verification", "ci_iv")).toBe("CI and independent verification");
    expect(viewLabel("chronicle", "telemetry")).toBe("Telemetry snapshot");
  });
});
