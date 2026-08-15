import type { ProjectBrief } from "../hooks/useLiveBrief";

/**
 * AS-CODER-ALPHA-CONTEXT-001 web paste pack.
 * Derived from the live brief projection. Not the CLI on-disk export.
 * Not authority. UNKNOWN stays UNKNOWN.
 */

export function flattenContextLine(value: unknown): string {
  if (typeof value !== "string") {
    return "UNKNOWN";
  }
  const flattened = value.replace(/[\r\n\t]+/g, " ").replace(/ +/g, " ").trim();
  return flattened || "UNKNOWN";
}

function sameProject(left: string, right: string): boolean {
  return left.trim() === right.trim();
}

function rowProjectId(row: object): string {
  if (!("project_id" in row)) {
    return "";
  }
  const pid = (row as { project_id?: unknown }).project_id;
  return typeof pid === "string" ? pid.trim() : "";
}

export function renderAgentContextMarkdown(
  brief: ProjectBrief,
  expectedProjectId?: string,
): string {
  const expected =
    typeof expectedProjectId === "string" ? expectedProjectId.trim() : "";
  const briefProject =
    typeof brief.project_id === "string" ? brief.project_id.trim() : "";
  if (expected && briefProject && !sameProject(briefProject, expected)) {
    return "";
  }
  const project = flattenContextLine(briefProject || expected);
  const next = Array.isArray(brief.suggested_next_work)
    ? brief.suggested_next_work
        .map((item) => flattenContextLine(item))
        .filter((item) => item !== "UNKNOWN")
    : [];
  const sessions = (brief.session_captures ?? []).filter((row) => {
    const pid = rowProjectId(row);
    return !pid || sameProject(pid, project);
  });
  const conversations = (brief.conversation_captures ?? []).filter((row) => {
    const pid = rowProjectId(row);
    return !pid || sameProject(pid, project);
  });
  const unknown = flattenContextLine(brief.unknown_or_conflicting);
  const lines = [
    `# Atlas agent context — ${project}`,
    "",
    "WEB_CONTEXT != ATLAS_CONTEXT_FILE",
    "UI != CANONICAL_TRUTH",
    "LENS != AUTHORITY",
    "UNKNOWN stays UNKNOWN",
    "DERIVED_CONTEXT != AUTHORITY",
    "",
    "## Purpose",
    flattenContextLine(brief.purpose),
    "",
    "## Current state",
    flattenContextLine(brief.current_state),
    "",
    "## What changed",
    flattenContextLine(brief.recent_meaningful_changes),
    "",
    "## Decisions",
    flattenContextLine(brief.important_decisions),
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
            `- [${flattenContextLine(row.kind)}] ${flattenContextLine(row.summary)} (authority=false)`,
        )
      : ["- UNKNOWN — no session captures"]),
    "",
    "## Conversation captures",
    ...(conversations.length > 0
      ? conversations.map(
          (row) =>
            `- [${flattenContextLine(row.review_state)}] ${flattenContextLine(row.summary)} (conversation≠authority)`,
        )
      : ["- UNKNOWN — no conversation captures"]),
    "",
    "## Honesty",
    "- authentic_pilot: false",
    "- atlas_opt_wake_gate: CLOSED",
    "- lens_is_authority: false",
    "- web_context_is_authority: false",
    "",
    flattenContextLine(
      brief.truth_boundary ??
        "ASK/BRIEF/CONTEXT != CANONICAL WRITE / UI!=TRUTH / != AUTHORITY",
    ),
    "",
  ];
  return lines.join("\n");
}
