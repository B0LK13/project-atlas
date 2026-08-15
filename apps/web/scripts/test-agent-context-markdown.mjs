#!/usr/bin/env node
/**
 * Runtime honesty gates for renderAgentContextMarkdown.
 * Imports the production helper (type-stripped). No vault writes.
 */
import assert from "node:assert/strict";
import { renderAgentContextMarkdown } from "../src/lib/agentContextMarkdown.ts";

const brief = {
  project_id: "harbor-api",
  purpose: "Local-first compiler",
  current_state: "active",
  recent_meaningful_changes: "context pack",
  important_decisions: "UI != canonical",
  unknown_or_conflicting: "datastore conflict",
  suggested_next_work: ["Triage reviews", ""],
  session_captures: [
    { kind: "milestone", summary: "first\n# injected", project_id: "harbor-api" },
    { kind: "note", summary: "other project", project_id: "nebula" },
  ],
  conversation_captures: [
    {
      review_state: "captured",
      summary: "quarantined\nitem",
      project_id: "harbor-api",
    },
    {
      review_state: "captured",
      summary: "leaked",
      project_id: "nebula",
    },
  ],
  truth_boundary: "WEB BRIEF READ != AUTHORITY / UI != CANONICAL",
};

const first = renderAgentContextMarkdown(brief, "harbor-api");
const second = renderAgentContextMarkdown(brief, "harbor-api");
assert.equal(first, second, "clipboard output must be deterministic");
assert.match(first, /^# Atlas agent context — harbor-api\n/);
assert.match(first, /LENS != AUTHORITY/);
assert.match(first, /DERIVED_CONTEXT != AUTHORITY/);
assert.match(first, /web_context_is_authority: false/);
assert.match(first, /## Unknown \/ conflicts\ndatastore conflict\n/);
assert.match(first, /- \[milestone\] first # injected \(authority=false\)/);
assert.doesNotMatch(first, /# injected\n/);
assert.doesNotMatch(first, /other project/);
assert.doesNotMatch(first, /leaked/);
assert.match(first, /quarantined item \(conversation≠authority\)/);

const empty = renderAgentContextMarkdown(
  { project_id: "nebula", purpose: "other" },
  "harbor-api",
);
assert.equal(empty, "", "cross-project brief must not produce a pack");

const missing = renderAgentContextMarkdown(
  { project_id: "harbor-api" },
  "harbor-api",
);
assert.match(missing, /## Purpose\nUNKNOWN\n/);
assert.match(missing, /## Unknown \/ conflicts\nUNKNOWN\n/);
assert.match(missing, /- UNKNOWN — no session captures/);
assert.match(missing, /- UNKNOWN — no conversation captures/);
assert.match(missing, /- UNKNOWN\n/);

console.log("agent-context-markdown runtime gates: PASS");
