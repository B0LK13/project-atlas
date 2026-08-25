import { Link } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useReadStatus } from "../../hooks/useReadStatus";

/** Production projects inventory — read-only; never invents PILOT rows. */
export default function ProjectsPage() {
  const { status, error, loading, dataSource } = useReadStatus();
  const projects = status?.projects ?? [];
  const isDemo = dataSource === "demo_stub" || status?.demo_isolated === true;

  return (
    <ProdShell>
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">Production · Projects</p>
          <h1>Projects</h1>
          <p className="lede">
            Read-only project inventory. LIVE_API preferred; demo stub isolated.
            Missing evidence stays unknown — never invented estate rows.
            Open Knowledge for the one-minute project brief, or Time Machine
            for conflicts and as-of history.
          </p>
        </header>

        {error ? <p className="banner warn">Inventory unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">DEMO STUB — isolated sample data · not live vault</p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Project inventory">
          <h2>Inventory</h2>
          {projects.length === 0 && !loading ? (
            <p className="banner warn">unknown — no project rows in read-status</p>
          ) : (
            <ul className="theme-hub">
              {projects.map((project) => {
                const id = project.project_id ?? "unnamed";
                return (
                  <li key={project.project_id ?? project.path ?? JSON.stringify(project)}>
                    <strong>
                      {project.project_id ? (
                        <Link to={`/knowledge?project=${encodeURIComponent(id)}`}>
                          {id}
                        </Link>
                      ) : (
                        id
                      )}
                    </strong>
                    <span>
                      {project.path ?? "path unknown"} ·{" "}
                      <Link to={`/knowledge?project=${encodeURIComponent(id)}`}>
                        Knowledge
                      </Link>
                      {" · "}
                      <Link to={`/time-machine?project=${encodeURIComponent(id)}`}>
                        Time Machine
                      </Link>
                      {" · "}
                      <Link to="/portfolio">Portfolio</Link>
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="disclaimer">
            UI ≠ canonical · Graph ≠ authority
            {isDemo ? " · demo isolated" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
