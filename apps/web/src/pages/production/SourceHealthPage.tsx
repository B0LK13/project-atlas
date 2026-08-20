import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import {
  type SourceHealthRow,
  useLiveSourceHealth,
} from "../../hooks/useLiveSourceHealth";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 — read-only source-health lens.
 * SOURCE HEALTH != AUTHORITY. UI != CANONICAL. UNKNOWN remains UNKNOWN.
 * Explicit ?project= only. No silent demo fallback presented as live.
 * No score theatre. No write controls.
 */

function textOrUnknown(value: unknown): string {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return "UNKNOWN";
}

function countOrUnknown(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? String(value)
    : "UNKNOWN";
}

function isUnknownState(state: string): boolean {
  const token = state.trim().toUpperCase();
  return token === "UNKNOWN" || token === "UNREADABLE" || token === "";
}

function RowList({
  rows,
  empty,
}: {
  rows: SourceHealthRow[];
  empty: string;
}) {
  if (rows.length === 0) {
    return <p className="banner warn">{empty}</p>;
  }
  return (
    <ul className="theme-hub">
      {rows.map((row, index) => {
        const reason = textOrUnknown(row.reason_code);
        const explanation = textOrUnknown(row.human_explanation);
        return (
          <li key={`${row.source ?? "row"}-${reason}-${index}`}>
            <strong>
              [{textOrUnknown(row.status)}] {textOrUnknown(row.source)}
            </strong>
            <span>
              reason_code={reason} · {explanation}
              {row.pipeline_stage
                ? ` · stage=${textOrUnknown(row.pipeline_stage)}`
                : ""}
              {row.suggested_next_action
                ? ` · next=${textOrUnknown(row.suggested_next_action)}`
                : ""}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export default function SourceHealthPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { report, error, loading, dataSource } = useLiveSourceHealth(projectId);
  const isDemo = dataSource === "demo_stub";
  const healthState = textOrUnknown(report?.health_state);
  const unknownHealth = isUnknownState(healthState);
  const reportProject =
    typeof report?.project_id === "string" ? report.project_id.trim() : "";
  const projectMismatch = Boolean(
    report && projectId && reportProject && reportProject !== projectId,
  );
  const unavailable = Boolean(error) || (!loading && Boolean(projectId) && !report && !isDemo);
  const actionable = report?.actionable ?? [];
  const reasonCounts = report?.reason_counts ?? {};
  const noiseGroups = report?.noise_groups ?? {};
  const artifactStatus = report?.artifact_status ?? {};

  function onSelectProject(next: string) {
    const nextParams = new URLSearchParams(params);
    if (next) {
      nextParams.set("project", next);
    } else {
      nextParams.delete("project");
    }
    setParams(nextParams, { replace: true });
  }

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Source Health · Coder Alpha</p>
          <h1>Source health</h1>
          <p className="lede">
            Read-only LIVE_API projection of why sources failed, were excluded,
            or quarantined for <code>{projectId ?? "UNKNOWN"}</code>. Reason
            codes and safe explanations only. Not authority. Not a score.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">source_health≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">score_theatre=false</span>
            <span className="chip">write_controls=false</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="source-health-project">
            Focus project (required — no implicit portfolio-all)
          </label>
          <select
            id="source-health-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            {!projectId ? (
              <option value="">unknown — select a project</option>
            ) : null}
            {projects.map((project) => (
              <option
                key={project.project_id ?? project.path}
                value={project.project_id ?? ""}
              >
                {project.project_id ?? "unnamed"}
              </option>
            ))}
            {projectId &&
            !projects.some((project) => project.project_id === projectId) ? (
              <option value={projectId}>{projectId}</option>
            ) : null}
          </select>
        </section>

        {!projectId ? (
          <p className="banner warn">
            UNKNOWN — explicit project required. Source health is not shown
            without <code>?project=</code>.
          </p>
        ) : null}
        {error ? (
          <p className="banner warn">
            Source health unavailable: {error} — LIVE_API degraded; not replaced
            with a demo presented as live
          </p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            live source-health (not vault truth; not presented as live)
          </p>
        ) : null}
        {unavailable ? (
          <p className="banner warn">
            DEGRADED / UNAVAILABLE — no live source-health payload for this
            project
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — source-health project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Health state">
          <h2>Health state</h2>
          <p className={unknownHealth || unavailable ? "banner warn" : "lede"}>
            {projectId
              ? `${healthState} — SOURCE HEALTH != AUTHORITY`
              : "UNKNOWN — no project selected · SOURCE HEALTH != AUTHORITY"}
          </p>
          <p className="flags">
            <span className="chip">
              diagnostic={textOrUnknown(report?.diagnostic)}
            </span>
            <span className="chip">
              authority={textOrUnknown(report?.authority ?? "derived")}
            </span>
            <span className="chip">
              sources={countOrUnknown(report?.source_count)}
            </span>
            <span className="chip">
              actionable={countOrUnknown(report?.actionable_count)}
            </span>
            <span className="chip">
              noise={countOrUnknown(report?.noise_count)}
            </span>
            <span className="chip">
              unscoped_omitted={countOrUnknown(report?.unscoped_omitted_count)}
            </span>
          </p>
          <p className="disclaimer">
            Counts are inventory, not scores. CLEAR is not certified healthy.
            UNKNOWN stays UNKNOWN. Secret content is never shown.
          </p>
        </section>

        <section className="panel" aria-label="Reason codes">
          <h2>Reason codes</h2>
          {Object.keys(reasonCounts).length === 0 ? (
            <p className="banner warn">
              {projectId
                ? "UNKNOWN — no reason_code inventory for this project"
                : "UNKNOWN — select a project"}
            </p>
          ) : (
            <ul className="theme-hub">
              {Object.entries(reasonCounts)
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([code, count]) => (
                  <li key={code}>
                    <strong>{code}</strong>
                    <span>count={count} · not a score</span>
                  </li>
                ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Actionable sources">
          <h2>Actionable sources</h2>
          <p className="lede">
            Each row shows <code>reason_code</code> plus the canned safe
            explanation. No secret echo. No accept / reject / promote.
          </p>
          {!projectId ? (
            <p className="banner warn">UNKNOWN — select a project</p>
          ) : (
            <RowList
              rows={actionable}
              empty="UNKNOWN — no actionable source-health rows"
            />
          )}
        </section>

        <section className="panel" aria-label="Noise groups">
          <h2>Noise groups</h2>
          {Object.keys(noiseGroups).length === 0 ? (
            <p>No collapsed noise groups on this lens.</p>
          ) : (
            <ul>
              {Object.entries(noiseGroups)
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([group, count]) => (
                  <li key={group}>
                    {group} · count={count}
                  </li>
                ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Inspected artifacts">
          <h2>Inspected artifacts</h2>
          {Object.keys(artifactStatus).length === 0 ? (
            <p className="banner warn">UNKNOWN — no artifact inspection</p>
          ) : (
            <ul>
              {Object.entries(artifactStatus)
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([name, state]) => (
                  <li key={name}>
                    {name}: {textOrUnknown(state)}
                  </li>
                ))}
            </ul>
          )}
        </section>

        <p className="disclaimer">
          UI ≠ canonical · SOURCE HEALTH ≠ AUTHORITY · UNKNOWN ≠ healthy ·
          {isDemo
            ? " demo isolated from LIVE_API"
            : " LIVE_API read-only GET /v1/source-health"}
          {report?.truth_boundary ? ` · ${report.truth_boundary}` : ""}
        </p>
      </main>
    </ProdShell>
  );
}
