import { ChevronRight } from "lucide-react";
import type { VerificationStagePreview } from "../types";
import { TruthBadge, WorkflowBadge } from "./StatusLanguage";
import { EmptyState } from "./EmptyState";

export function VerificationPipeline({
  stages,
  detailed = false,
}: {
  stages: VerificationStagePreview[];
  detailed?: boolean;
}) {
  if (!stages.length) {
    return <EmptyState title="Verification not started" detail="No evidence-bound verification stages were projected." />;
  }
  return (
    <ol className={`verification-pipeline ${detailed ? "pipeline-detailed" : ""}`} aria-label="Verification pipeline">
      {stages.map((stage, index) => (
        <li key={stage.id} className={`pipeline-stage stage-${stage.state.toLowerCase().replaceAll("_", "-")}`}>
          <div className="pipeline-index">{String(index + 1).padStart(2, "0")}</div>
          <div className="pipeline-stage-body">
            <span className="pipeline-label">{stage.label}</span>
            {detailed ? <p>{stage.detail}</p> : null}
            <div className="pipeline-meta">
              <WorkflowBadge state={stage.state} />
              {detailed ? <TruthBadge state={stage.truth} compact /> : null}
            </div>
          </div>
          {index < stages.length - 1 ? <ChevronRight className="pipeline-arrow" size={14} aria-hidden="true" /> : null}
        </li>
      ))}
    </ol>
  );
}
