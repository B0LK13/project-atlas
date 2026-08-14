import type { ProjectBrief } from "../hooks/useLiveBrief";

/**
 * AS-CODER-ALPHA-CONTEXT-001 web paste pack.
 * Derived from the live brief projection. Not the CLI on-disk export.
 * Not authority. UNKNOWN stays UNKNOWN.
 */

function line(value: unknown): string {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  return "UNKNOWN";
}

export function renderAgentContextMarkdown(brief: ProjectBrief): string {
  const project = line(brief.project_id);
  const next = Array.isArray(brief.suggested_next_work)
    ? brief.suggested_next_work.filter((item) => item.trim())
    : [];
  const sessions = brief.session_captures ?? [];
  const conversations = brief.conversation_captures ?? [];
  const unknown = line(brief.unknown_or_conflicting);
  const lines = [
    `# Atlas agent context — ${project}`,
    "",
    "WEB_CONTEXT != ATLAS_CONTEXT_FILE",
    "UI != CANONICAL_TRUTH",
    "LENS != AUTHORITY",
    "UNKNOWN stays UNKNOWN",
    "",
    "## Purpose",
    line(brief.purpose),
    "",
    "## Current state",
    line(brief.current_state),
    "",
    "## What changed",
    line(brief.recent_meaningful_changes),
    "",
    "## Decisions",
    line(brief.important_decisions),
    "",
    "## Unknown / conflicts",
    unknown,
    "",
    "## Next work",
    ...(next.length > 0 ? next.map((item) => `- ${item}`) : ["- UNKNOWN"]),
    "",
    "## Session captures",
    ...(sessions.length > 0
      ? sessions.map(
          (row) =>
            `- [${line(row.kind)}] ${line(row.summary)} (authority=false)`,
        )
      : ["- UNKNOWN — no session captures"]),
    "",
    "## Conversation captures",
    ...(conversations.length > 0
      ? conversations.map(
          (row) =>
            `- [${line(row.review_state)}] ${line(row.summary)} (conversation≠authority)`,
        )
      : ["- UNKNOWN — no conversation captures"]),
    "",
    brief.truth_boundary ??
      "ASK/BRIEF/CONTEXT != CANONICAL WRITE / UI!=TRUTH / != AUTHORITY",
    "",
  ];
  return lines.join("\n");
}
