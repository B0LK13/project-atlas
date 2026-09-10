import type { ScreenId } from "../types";

const PURPOSES: Partial<Record<ScreenId, { question: string; intro: string }>> = {
  agents: { question: "Which agents are observed, and what work is associated with them?", intro: "Registered activity and ownership are observations; they do not prove running execution." },
  "work-graph": { question: "What dependencies explain the current work state?", intro: "This view shows the frontier and ownership data supplied by the source; missing edges stay unknown." },
  repository: { question: "What is the repository and stack state?", intro: "Inspect the source repository identity and stack records; no file explorer is connected here." },
  verification: { question: "Which candidates have evidence, and what gate remains?", intro: "CI, independent verification, owner authorization, and post-merge sealing remain separate source states." },
  knowledge: { question: "What knowledge and provenance can I inspect?", intro: "This route reports the connected knowledge capability and its evidence boundary." },
  chronicle: { question: "What happened over time?", intro: "Telemetry is a current snapshot unless event records are supplied by the source." },
  projects: { question: "What project context is available?", intro: "This is the selected project readout; a project catalog is not inferred from one source." },
};

export function pagePurpose(screen: ScreenId): { question: string; intro: string } {
  return PURPOSES[screen] ?? { question: "What does this source provide?", intro: "The source defines the available detail and its limits." };
}

export function secondaryAttentionLabel(count: number): string {
  return count ? `${count} attention items · open Mission Control` : "No attention items supplied · open Mission Control";
}

const VIEW_LABELS: Record<string, string> = {
  agents_lanes: "Observed agent directory",
  ownership: "Ownership records",
  frontier: "Frontier action summary",
  human_gates: "Owner decision gates",
  ci_iv: "CI and independent verification",
  postmerge_seal: "Post-merge seal",
  evidence: "Evidence records",
  stacks: "Repository stack records",
  telemetry: "Telemetry snapshot",
  health: "Source health",
  residuals: "Residual findings",
};

export function viewLabel(_screen: ScreenId, key: string): string {
  return VIEW_LABELS[key] ?? key.replaceAll("_", " ");
}
