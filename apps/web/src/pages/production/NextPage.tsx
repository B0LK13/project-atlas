import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveNext } from "../../hooks/useLiveNext";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-NEXT-WEB-001 — derived daily What Next lens.
 * UI ≠ canonical; NEXT ≠ authority; NEXT ≠ command; UNKNOWN ≠ healthy.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function NextPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { next, error, loading, dataSource } = useLiveNext(projectId);
  const isDemo = dataSource === "demo_stub";
  const primary = next?.primary;
  const queue = next?.queue ?? [];
  const blockers = next?.blockers ?? [];
  const suggested = next?.suggested_next_work ?? [];
  const lensProject =
    typeof next?.project_id === "string" ? next.project_id.trim() : "";
  const projectMismatch = Boolean(
    next && projectId && lensProject && lensProject !== projectId,
  );

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
          <p className="eyebrow">Production · Coder Alpha What Next</p>
          <h1>What next</h1>
          <p className="lede">
            Derived suggestion of what should happen next for{" "}
            <code>{projectId ?? "UNKNOWN"}</code>. Not a command. Not
            authority. Unknown is valid. No invented work.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">next≠authority</span>
            <span className="chip">next≠command</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="next-project">
            Focus project
          </label>
          <select
            id="next-project"
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

        {error ? <p className="banner warn">What Next unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            a live derived What Next lens (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — next project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Primary next">
          <h2>Primary</h2>
          {!loading && !primary ? (
            <p className="banner warn">UNKNOWN — no next evidence</p>
          ) : (
            <p>
              <strong>{primary?.title ?? next?.summary ?? "UNKNOWN"}</strong> [
              {primary?.kind ?? next?.status ?? "UNKNOWN"}]
              <span> · {primary?.why ?? "unknown"}</span>
            </p>
          )}
          {next?.why_cannot_advance ? (
            <p className="banner warn">
              Blocked: {next.why_cannot_advance}
            </p>
          ) : null}
        </section>

        <section className="panel" aria-label="Suggested next work">
          <h2>Suggested next work</h2>
          {suggested.length === 0 ? (
            <p className="banner warn">UNKNOWN — no suggested work</p>
          ) : (
            <ul>
              {suggested.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
          <p className="lede">These lines are suggestions, not commands.</p>
        </section>

        <section className="panel" aria-label="Blockers">
          <h2>Blockers</h2>
          {blockers.length === 0 ? (
            <p>No derived blockers on this lens.</p>
          ) : (
            <ul>
              {blockers.map((blocker, index) => (
                <li key={`${blocker.kind ?? "none"}-${index}`}>
                  [{blocker.kind ?? "UNKNOWN"}] {blocker.title ?? "UNKNOWN"}
                  {blocker.why ? ` · ${blocker.why}` : ""}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Queue">
          <h2>Queue</h2>
          {queue.length === 0 ? (
            <p className="banner warn">UNKNOWN — empty next queue</p>
          ) : (
            <ul className="theme-hub">
              {queue.map((item, index) => (
                <li key={`${item.kind ?? "item"}-${index}`}>
                  <strong>[{item.kind ?? "UNKNOWN"}]</strong>
                  <span>
                    {" "}
                    {item.title ?? "UNKNOWN"}
                    {item.action ? ` — ${item.action}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </ProdShell>
  );
}
