import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveOverview } from "../../hooks/useLiveOverview";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-OVERVIEW-WEB-001 — derived Project Overview lens.
 * UI ≠ canonical; OVERVIEW ≠ authority; UNKNOWN ≠ healthy.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function OverviewPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { overview, error, loading, dataSource } = useLiveOverview(projectId);
  const isDemo = dataSource === "demo_stub";
  const coverage = overview?.coverage ?? {};
  const notes = overview?.notes ?? [];
  const lensProject =
    typeof overview?.project_id === "string" ? overview.project_id.trim() : "";
  const projectMismatch = Boolean(
    overview && projectId && lensProject && lensProject !== projectId,
  );
  const lensStatus = overview?.status ?? "unknown";

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
          <p className="eyebrow">Production · Coder Alpha Overview</p>
          <h1>Overview</h1>
          <p className="lede">
            Derived project overview for{" "}
            <code>{projectId ?? "UNKNOWN"}</code>. Overview is not authority.
            Unknown is never healthy.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">overview≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="overview-project">
            Focus project
          </label>
          <select
            id="overview-project"
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

        {error ? <p className="banner warn">Overview unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            a live derived overview (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — overview project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Overview lens">
          <h2>What is this project?</h2>
          {!loading && !overview ? (
            <p className="banner warn">UNKNOWN — no overview evidence</p>
          ) : null}
          {overview ? (
            <p className="lede">
              <strong>{overview.title ?? "What is this project?"}</strong> [
              {lensStatus}]
              <span> · {overview.summary ?? "UNKNOWN"}</span>
            </p>
          ) : null}
          {lensStatus === "unknown" ? (
            <p className="banner warn">UNKNOWN — overview value is not invented</p>
          ) : null}
        </section>

        <section className="panel" aria-label="Coverage">
          <h2>Coverage</h2>
          {Object.keys(coverage).length === 0 ? (
            <p className="banner warn">UNKNOWN — no coverage rows</p>
          ) : (
            <ul>
              {Object.entries(coverage).map(([category, state]) => (
                <li key={category}>
                  {category}: {state}
                </li>
              ))}
            </ul>
          )}
          {notes.length === 0 ? (
            <p className="lede">Notes stay unknown when absent.</p>
          ) : (
            <ul>
              {notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </ProdShell>
  );
}
