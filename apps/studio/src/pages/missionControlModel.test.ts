import { describe, expect, it } from "vitest";
import type { AttentionItem } from "../types";
import { groupAttention, attentionLabel, metricLabel, freshnessLabel } from "./missionControlModel";

const item = (id: string, kind: string, title = kind): AttentionItem => ({
  attention_id: id, kind, tier: 60, title, detail: `${kind} detail`, attention_ne_authorization: true,
});

describe("mission control decision support", () => {
  it("groups by the source supplied cause while retaining every record", () => {
    const groups = groupAttention([item("a", "PANEL_STATUS"), item("b", "PANEL_STATUS"), item("c", "HUMAN_GATE")]);
    expect(groups.map((group) => [group.cause, group.items.length])).toEqual([["PANEL_STATUS", 2], ["HUMAN_GATE", 1]]);
    expect(groups.flatMap((group) => group.items).map((entry) => entry.attention_id)).toEqual(["a", "b", "c"]);
  });

  it("translates known source states and preserves the exact value", () => {
    expect(attentionLabel(item("a", "EXTERNAL_IV_GATED")).primary).toBe("Independent verification unavailable");
    expect(attentionLabel(item("b", "HUMAN_GATE", "Human gate action: pr/793:OWNER_DECISION")).primary).toContain("Owner decision needed");
    expect(attentionLabel(item("c", "UNSEEN_CAUSE")).exact).toBe("UNSEEN_CAUSE");
  });

  it("names metrics by their actual entity and keeps freshness precise", () => {
    expect(metricLabel("eligible_count")).toBe("Frontier actions eligible");
    expect(metricLabel("active_count")).toBe("Agents listed active");
    expect(freshnessLabel({ state: "STALE", age_seconds: 90, generated_at_utc: "2026-09-10T09:00:00Z", snapshot_fingerprint: "fp", max_age_seconds: 60 })).toContain("Updated 1 minute ago");
  });
});
