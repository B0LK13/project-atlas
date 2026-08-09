import { ProdShell } from "../../components/ProdShell";
import { useReadStatus } from "../../hooks/useReadStatus";

/** Production projects inventory — read-only; never invents PILOT rows. */
export default function ProjectsPage() {
  const { status, error, loading } = useReadStatus();
  const projects = status?.projects ?? [];

  return (
    <ProdShell>
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">Production · Projects</p>
          <h1>Projects</h1>
          <p className="lede">
            Read-only project inventory from the sample/read adapter. Missing
            evidence stays unknown — never invented estate rows.
          </p>
        </header>

        {error ? <p className="banner warn">Inventory unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}

        <section className="panel" aria-label="Project inventory">
          <h2>Inventory</h2>
          {projects.length === 0 && !loading ? (
            <p className="banner warn">unknown — no project rows in read-status</p>
          ) : (
            <ul className="theme-hub">
              {projects.map((project) => (
                <li key={project.project_id ?? project.path ?? JSON.stringify(project)}>
                  <strong>{project.project_id ?? "unnamed"}</strong>
                  <span>{project.path ?? "sample row"}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="disclaimer">UI ≠ canonical · sample/adapter only</p>
        </section>
      </main>
    </ProdShell>
  );
}
