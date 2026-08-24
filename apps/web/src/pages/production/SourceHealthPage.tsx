import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveSourceHealth } from "../../hooks/useLiveSourceHealth";
import { useReadStatus } from "../../hooks/useReadStatus";

const WARN_STATES = new Set([
  "UNKNOWN",
  "UNREADABLE",
  "ACTION_REQUIRED",
  "STALE",
]);

/**
 * AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 — derived source-health lens.
 * UI ≠ canonical; SOURCE HEALTH ≠ authority; UNKNOWN ≠ healthy.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function SourceHealthPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { report, error, loading, dataSource } = useLiveSourceHealth(projectId);
  const isDemo = dataSource === "demo_stub";
  const healthState = (report?.health_state ?? "UNKNOWN").toUpperCase();
  const warnState = WARN_STATES.has(healthState);
  const reportProject =
    typeof report?.project_id === "string" ? report.project_id.trim() : "";
  const projectMismatch = Boolean(
    report && projectId && reportProject && reportProject !== projectId,
  );
  const actionable = report?.actionable ?? [];
  const noise = report?.noise ?? [];

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
          <p className="eyebrow">Production · Source health</p>
          <h1>Source health</h1>
          <p className="lede">
            Derived explainability for excluded, quarantined, and failed sources
            on <code>{projectId ?? "UNKNOWN"}</code>. Not canonical truth. Not
            authority. UNKNOWN is never healthy. Secrets are never echoed.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">source_health≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="source-health-project">
            Focus project
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

        {error ? (
          <p className="banner warn">Source health unavailable: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            live derived source health (not vault truth)
          </p>
        ) : null}
        {!projectId && !isDemo ? (
          <p className="banner warn">
            UNKNOWN — select a project. No implicit portfolio-all.
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — source-health project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Health state">
          <h2>Health state</h2>
          {!loading && !report && !error && projectId ? (
            <p className="banner warn">UNKNOWN — no source-health evidence</p>
          ) : (
            <p className={warnState ? "banner warn" : undefined}>
              <strong>{healthState}</strong>
              <span>
                {" "}
                · diagnostic={report?.diagnostic ?? "UNKNOWN"} · actionable=
                {report?.actionable_count ?? 0} · noise={report?.noise_count ?? 0}
              </span>
            </p>
          )}
          {report?.honesty?.unreadable_as_healthy === true ? (
            <p className="banner warn">
              INVALID — unreadable must not be presented as healthy
            </p>
          ) : null}
        </section>

        <section className="panel" aria-label="Actionable sources">
          <h2>Actionable</h2>
          {actionable.length === 0 ? (
            <p>
              {healthState === "UNKNOWN" || healthState === "UNREADABLE"
                ? "UNKNOWN — no positively inspected actionable sources"
                : "No actionable source failures on this derived lens."}
            </p>
          ) : (
            <ul className="theme-hub">
              {actionable.map((row, index) => (
                <li key={`${row.source ?? "unknown"}-${index}`}>
                  <strong>{row.source ?? "UNKNOWN"}</strong>
                  <span>
                    [{row.status ?? "UNKNOWN"} / {row.pipeline_stage ?? "UNKNOWN"}]{" "}
                    {row.reason_code ?? "UNCLASSIFIED"}
                    {row.human_explanation ? ` · ${row.human_explanation}` : ""}
                    {row.suggested_next_action
                      ? ` · next: ${row.suggested_next_action}`
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Noise / exclusions">
          <h2>Noise</h2>
          {noise.length === 0 ? (
            <p>No excluded/noise rows on this derived lens.</p>
          ) : (
            <ul>
              {noise.map((row, index) => (
                <li key={`${row.source ?? "noise"}-${index}`}>
                  {row.source ?? "UNKNOWN"} · {row.reason_code ?? "excluded"}
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </ProdShell>
  );
}
