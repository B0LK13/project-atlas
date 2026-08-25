import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveState } from "../../hooks/useLiveState";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-STATE-WEB-001 — derived Current State lens.
 * UI ≠ canonical; STATE ≠ authority; UNKNOWN ≠ healthy.
 * Distinct from intelligence /v1/project-state.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function StatePage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { state, error, loading, dataSource } = useLiveState(projectId);
  const isDemo = dataSource === "demo_stub";
  const signals = state?.signals ?? {};
  const lensProject =
    typeof state?.project_id === "string" ? state.project_id.trim() : "";
  const projectMismatch = Boolean(
    state && projectId && lensProject && lensProject !== projectId,
  );
  const rollup = state?.rollup ?? "unknown";

  function onSelectProject(nextProject: string) {
    const nextParams = new URLSearchParams(params);
    if (nextProject) {
      nextParams.set("project", nextProject);
    } else {
      nextParams.delete("project");
    }
    setParams(nextParams, { replace: true });
  }

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Coder Alpha State</p>
          <h1>Current state</h1>
          <p className="lede">
            Derived current-state lens for{" "}
            <code>{projectId ?? "UNKNOWN"}</code>. State is not authority.
            Rollup is not a trust score. This is not project-state.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">state≠authority</span>
            <span className="chip">rollup≠trust</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="state-project">
            Focus project
          </label>
          <select
            id="state-project"
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

        {error ? <p className="banner warn">State unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            a live derived state lens (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — state project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="State lens">
          <h2>What is the current state?</h2>
          {!loading && !state ? (
            <p className="banner warn">UNKNOWN — no state evidence</p>
          ) : null}
          {state ? (
            <p className="lede">
              <strong>{state.title ?? "What is the current state?"}</strong> [
              {rollup}]
              <span> · {state.summary ?? "UNKNOWN"}</span>
            </p>
          ) : null}
          {rollup === "unknown" || rollup === "UNKNOWN" ? (
            <p className="banner warn">UNKNOWN — state rollup is not invented healthy</p>
          ) : null}
          <dl>
            <div>
              <dt>lifecycle</dt>
              <dd>{state?.lifecycle ?? "unknown"}</dd>
            </div>
            <div>
              <dt>pending_reviews</dt>
              <dd>{String(signals.pending_reviews ?? "unknown")}</dd>
            </div>
            <div>
              <dt>unresolved_conflicts</dt>
              <dd>{String(signals.unresolved_conflicts ?? "unknown")}</dd>
            </div>
            <div>
              <dt>stale_claims</dt>
              <dd>{String(signals.stale_claims ?? "unknown")}</dd>
            </div>
            <div>
              <dt>sources_failed</dt>
              <dd>{String(signals.sources_failed ?? "unknown")}</dd>
            </div>
          </dl>
          <p className="lede">These signals are observations, not owner grants.</p>
        </section>
      </main>
    </ProdShell>
  );
}
