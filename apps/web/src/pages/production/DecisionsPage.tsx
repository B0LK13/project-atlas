import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveDecisions } from "../../hooks/useLiveDecisions";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-DECISIONS-WEB-001 — derived Decision memory lens.
 * UI ≠ canonical; DECISIONS ≠ authority; ACTIVE_GOVERNING ≠ trust score.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function DecisionsPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { decisions, error, loading, dataSource } = useLiveDecisions(projectId);
  const isDemo = dataSource === "demo_stub";
  const rows = decisions?.decisions ?? [];
  const lensProject =
    typeof decisions?.project_id === "string" ? decisions.project_id.trim() : "";
  const projectMismatch = Boolean(
    decisions && projectId && lensProject && lensProject !== projectId,
  );
  const lensStatus = decisions?.status ?? "unknown";

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
          <p className="eyebrow">Production · Coder Alpha Decisions</p>
          <h1>Decisions</h1>
          <p className="lede">
            Derived decision memory for{" "}
            <code>{projectId ?? "UNKNOWN"}</code>. Decisions are not authority.
            Active governing is not a trust score.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">decisions≠authority</span>
            <span className="chip">active_governing≠trust</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="decisions-project">
            Focus project
          </label>
          <select
            id="decisions-project"
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
          <p className="banner warn">Decisions unavailable: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            a live derived decisions lens (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — decisions project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Decision rows">
          <h2>What decisions matter?</h2>
          {!loading && !decisions ? (
            <p className="banner warn">UNKNOWN — no decisions evidence</p>
          ) : null}
          {decisions ? (
            <p className="lede">
              <strong>{decisions.title ?? "What decisions matter?"}</strong> [
              {lensStatus}] · count={String(decisions.decision_count ?? "unknown")}{" "}
              · active_governing=
              {String(decisions.active_governing_count ?? "unknown")}
            </p>
          ) : null}
          {lensStatus === "unknown" ? (
            <p className="banner warn">UNKNOWN — no governing decision evidence</p>
          ) : null}
          {rows.length === 0 ? (
            <p className="banner warn">UNKNOWN — no decision rows</p>
          ) : (
            <ul>
              {rows.map((item) => (
                <li key={`${item.title ?? "unknown"}-${item.source ?? "src"}`}>
                  [{item.status ?? "UNKNOWN"}] {item.title ?? "UNKNOWN"}
                  <span>
                    {" "}
                    · {item.authority ?? "unknown"} · {item.source ?? "unknown"}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="lede">These rows are observations, not owner grants.</p>
        </section>
      </main>
    </ProdShell>
  );
}
