import type { AttentionItem, MissionControlProjection } from "../types";

export interface AttentionGroup {
  cause: string;
  items: AttentionItem[];
}

/** Group only on the source's cause value; no priority or unlock meaning is inferred. */
export function groupAttention(items: AttentionItem[]): AttentionGroup[] {
  const groups = new Map<string, AttentionItem[]>();
  for (const item of items) {
    const cause = item.kind || "UNKNOWN";
    const bucket = groups.get(cause) ?? [];
    bucket.push(item);
    groups.set(cause, bucket);
  }
  return [...groups.entries()].map(([cause, grouped]) => ({ cause, items: grouped }));
}

/** Search only records loaded in the current projection. */
export function filterAttention(items: AttentionItem[], query: string): AttentionItem[] {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return items;
  return items.filter((item) => [
    item.attention_id,
    item.kind,
    item.title,
    item.detail,
    ...(item.references ?? []).map((reference) => `${reference.kind} ${reference.id}`),
  ].some((value) => String(value ?? "").toLocaleLowerCase().includes(needle)));
}

export function attentionLabel(item: AttentionItem): { primary: string; exact: string } {
  if (item.kind === "EXTERNAL_IV_GATED") return { primary: "Independent verification unavailable", exact: item.kind };
  if (item.kind === "HUMAN_GATE") {
    const match = item.title.match(/pr\/\d+/i);
    return { primary: match ? `Owner decision needed · ${match[0].toUpperCase()}` : "Owner decision needed", exact: item.kind };
  }
  if (item.kind === "BLOCKED_HIGH_VALUE") return { primary: "Blocked work needs inspection", exact: item.kind };
  if (item.kind === "PANEL_STATUS") return { primary: "Projection status needs inspection", exact: item.kind };
  return { primary: item.title || "Attention item", exact: item.kind || "UNKNOWN" };
}

/** A group heading names the source cause, never the first record's title. */
export function attentionGroupLabel(cause: string): string {
  if (cause === "HUMAN_GATE") return "Owner decisions";
  if (cause === "EXTERNAL_IV_GATED") return "Independent verification unavailable";
  if (cause === "BLOCKED_HIGH_VALUE") return "Blocked work";
  if (cause === "PANEL_STATUS") return "Projection status";
  return cause.replaceAll("_", " ").toLowerCase().replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
}

const METRIC_LABELS: Record<string, string> = {
  eligible_count: "Frontier actions eligible",
  blocked_count: "Frontier actions blocked",
  active_count: "Agents listed active",
  waiting_ci: "Actions waiting on CI",
  waiting_iv: "Actions waiting on independent verification",
};

export function metricLabel(key: string): string {
  return METRIC_LABELS[key] ?? key.replaceAll("_", " ");
}

export function freshnessLabel(freshness: MissionControlProjection["freshness"]): string {
  const age = freshness.age_seconds;
  if (typeof age === "number" && Number.isFinite(age)) {
    if (age < 60) return "Updated less than 1 minute ago";
    return `Updated ${Math.floor(age / 60)} minute${Math.floor(age / 60) === 1 ? "" : "s"} ago`;
  }
  if (freshness.state === "STALE") return "Source is stale · update age unavailable";
  if (freshness.state === "UNKNOWN") return "Source age unknown";
  return "Source update age unavailable";
}

export function sourceStateLabel(state: string): string {
  if (state === "LIVE") return "Connected read · source age shown below";
  if (state === "STALE") return "Stale source · inspect before relying on it";
  if (state === "OFFLINE" || state === "UNAVAILABLE") return "Disconnected · source unavailable";
  return "Source state unknown";
}
