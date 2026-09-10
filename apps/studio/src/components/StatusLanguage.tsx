import {
  Activity,
  CircleDashed,
  Clock3,
  Diamond,
  Eye,
  FlaskConical,
  GitMerge,
  HelpCircle,
  LockKeyhole,
  OctagonAlert,
  Play,
  ShieldCheck,
  Square,
  Triangle,
} from "lucide-react";
import type { TruthState, WorkflowState } from "../types";

const truthIcons = {
  OBSERVED: Eye,
  DERIVED: Diamond,
  INFERRED: Triangle,
  SIMULATED: FlaskConical,
  UNKNOWN: HelpCircle,
  CONTESTED: OctagonAlert,
  STALE: Clock3,
} satisfies Record<TruthState, typeof Eye>;

const workflowIcons = {
  RUNNING: Activity,
  READY: Play,
  BLOCKED: LockKeyhole,
  OWNER_REQUIRED: ShieldCheck,
  WAITING_FOR_CI: Clock3,
  WAITING_FOR_IV: CircleDashed,
  VERIFIED: ShieldCheck,
  FAILED: OctagonAlert,
  MERGED: GitMerge,
  SEALED: Square,
  UNKNOWN: HelpCircle,
} satisfies Record<WorkflowState, typeof Eye>;

export function TruthBadge({ state, compact = false }: { state: TruthState; compact?: boolean }) {
  const Icon = truthIcons[state];
  return (
    <span className={`truth-badge truth-${state.toLowerCase()} ${compact ? "is-compact" : ""}`}>
      <Icon size={compact ? 11 : 12} strokeWidth={2} aria-hidden="true" />
      <span>{state}</span>
    </span>
  );
}

export function WorkflowBadge({ state }: { state: WorkflowState }) {
  const Icon = workflowIcons[state];
  return (
    <span className={`workflow-badge workflow-${state.toLowerCase().replaceAll("_", "-")}`}>
      <Icon size={12} strokeWidth={2} aria-hidden="true" />
      <span>{state.replaceAll("_", " ")}</span>
    </span>
  );
}

export function AuthorityMark({ authorized, ownsLane }: { authorized: boolean; ownsLane: boolean }) {
  if (!authorized) {
    return (
      <span className="authority-mark authority-none">
        <CircleDashed size={12} aria-hidden="true" /> no authority
      </span>
    );
  }
  return (
    <span className={`authority-mark ${ownsLane ? "authority-owned" : "authority-scoped"}`}>
      <ShieldCheck size={12} aria-hidden="true" /> {ownsLane ? "lane owner" : "scoped"}
    </span>
  );
}
