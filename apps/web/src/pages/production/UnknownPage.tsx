import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveUnknown } from "../../hooks/useLiveUnknown";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-UNKNOWN-WEB-001 — derived unknown/conflict lens.
 * UI ≠ canonical; UNKNOWN ≠ healthy; UNKNOWN ≠ authority.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function UnknownPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { unknown, error, loading, dataSource } = useLiveUnknown(projectId);
  const isDemo = dataSource === "demo_stub";
  const items = unknown?.signals?.unknown_items ?? [];
  const lensProject =
    typeof unknown?.project_id === "string" ? unknown.project_id.trim() : "";
  const projectMismatch = Boolean(
    unknown && projectId && lensProject && lensProject !== projectId,
  );
  const rollup = unknown?.rollup ?? "unknown";

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
          <p className="eyebrow">Production · Coder Alpha Unknown</p>
          <h1>What is unknown</h1>
          <p className="lede">
            Derived unknown/conflict lens for{" "}
            <code>{projectId ?? "UNKNOWN"}</code>. Not authority. Unknown is
            valid and is never healthy. No invented answers.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">unknown≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="unknown-project">
            Focus project
          </label>
          <select
            id="unknown-project"
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
          <p className="banner warn">Unknown lens unavailable: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            a live derived unknown lens (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — unknown project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Unknown rollup">
          <h2>Rollup</h2>
          {!loading && !unknown ? (
            <p className="banner warn">UNKNOWN — no unknown evidence</p>
          ) : (
            <p>
              <strong>{unknown?.title ?? "What is unknown or conflicting?"}</strong>{" "}
              [{rollup}]
              <span> · {unknown?.summary ?? "unknown"}</span>
            </p>
          )}
          <p className="lede">
            Rollup is not a trust score. CLEAR is not healthy by default.
          </p>
        </section>

        <section className="panel" aria-label="Unknown signals">
          <h2>Signals</h2>
          {!unknown ? (
            <p className="banner warn">UNKNOWN — no signal counts</p>
          ) : (
            <dl>
              <dt>Pending reviews</dt>
              <dd>{String(unknown.signals?.pending_reviews ?? "unknown")}</dd>
              <dt>Unresolved conflicts</dt>
              <dd>{String(unknown.signals?.unresolved_conflicts ?? "unknown")}</dd>
              <dt>Stale claims</dt>
              <dd>{String(unknown.signals?.stale_claims ?? "unknown")}</dd>
              <dt>Sources failed</dt>
              <dd>{String(unknown.signals?.sources_failed ?? "unknown")}</dd>
            </dl>
          )}
        </section>

        <section className="panel" aria-label="Unknown items">
          <h2>Unknown items</h2>
          {items.length === 0 ? (
            <p className="banner warn">UNKNOWN — no unknown item rows</p>
          ) : (
            <ul>
              {items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </ProdShell>
  );
}
