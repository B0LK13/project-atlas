import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveChanged } from "../../hooks/useLiveChanged";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-CHANGED-WEB-001 — derived What Changed lens.
 * UI ≠ canonical; CHANGED ≠ kdiff; UNKNOWN history ≠ UNCHANGED.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function ChangedPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { changed, error, loading, dataSource } = useLiveChanged(projectId);
  const isDemo = dataSource === "demo_stub";
  const added = changed?.delta?.added ?? [];
  const removed = changed?.delta?.removed ?? [];
  const modified = changed?.delta?.modified ?? [];
  const semantic = changed?.semantic?.signals ?? [];
  const lensProject =
    typeof changed?.project_id === "string" ? changed.project_id.trim() : "";
  const projectMismatch = Boolean(
    changed && projectId && lensProject && lensProject !== projectId,
  );
  const rollup = changed?.rollup ?? "unknown";
  const liveDrift = changed?.source_drift?.status ?? "unknown";

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
          <p className="eyebrow">Production · Coder Alpha What Changed</p>
          <h1>What changed</h1>
          <p className="lede">
            Derived last-connect inventory lens for{" "}
            <code>{projectId ?? "UNKNOWN"}</code>. Not Time Machine. Not
            authority. Missing history stays unknown, never invented unchanged.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">changed≠kdiff</span>
            <span className="chip">changed≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="changed-project">
            Focus project
          </label>
          <select
            id="changed-project"
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
          <p className="banner warn">What Changed unavailable: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            a live derived What Changed lens (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — changed project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Changed rollup">
          <h2>Rollup</h2>
          {!loading && !changed ? (
            <p className="banner warn">UNKNOWN — no changed evidence</p>
          ) : (
            <p>
              <strong>{changed?.title ?? "What changed?"}</strong> [{rollup}]
              <span> · {changed?.summary ?? "unknown"}</span>
            </p>
          )}
          {liveDrift === "STALE" && rollup === "unchanged" ? (
            <p className="banner warn">
              STALE LIVE != UNCHANGED — reconnect before treating this as current
            </p>
          ) : null}
          <p className="lede">
            This is not <code>/v1/kdiff</code>. Baseline without a prior
            inventory is UNKNOWN history.
          </p>
        </section>

        <section className="panel" aria-label="Semantic signals">
          <h2>Know about</h2>
          {semantic.length === 0 ? (
            <p className="banner warn">UNKNOWN — no semantic change signals</p>
          ) : (
            <ul>
              {semantic.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Inventory delta">
          <h2>Inventory delta</h2>
          {added.length === 0 && removed.length === 0 && modified.length === 0 ? (
            <p className="banner warn">UNKNOWN — no inventory delta rows</p>
          ) : (
            <ul>
              {added.map((path) => (
                <li key={`added-${path}`}>added · {path}</li>
              ))}
              {removed.map((path) => (
                <li key={`removed-${path}`}>removed · {path}</li>
              ))}
              {modified.map((path) => (
                <li key={`modified-${path}`}>modified · {path}</li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </ProdShell>
  );
}
