import { LabShell } from "../../components/LabShell";
import { useReadStatus } from "../../hooks/useReadStatus";

/** Theme C — Cartograph Quiet (design-lab prototype). */
export default function CartographQuietPage() {
  const { status, error, loading } = useReadStatus();

  return (
    <LabShell theme="cartograph-quiet" className="theme-cartograph">
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">Design lab · Theme C</p>
          <h1>Cartograph Quiet</h1>
          <p className="lede">
            Soft map-grid field. Projects as quiet waypoints; health as a legend
            key. Any edges later are labeled derived only — graph ≠ authority.
          </p>
        </header>

        {error ? <p className="banner warn">Read status unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading read status…</p> : null}

        {status ? (
          <section className="panel" aria-label="Cartograph read status">
            <h2>Waypoints</h2>
            {status.projects.length === 0 ? (
              <p className="empty">No waypoints (honest empty).</p>
            ) : (
              <ul className="waypoint">
                {status.projects.map((project) => (
                  <li key={project.project_id}>
                    ◆ {project.project_id}
                    {project.has_project_note ? " · note" : " · unmarked"}
                  </li>
                ))}
              </ul>
            )}
            <div className="legend" aria-label="Health legend">
              <span>
                <i aria-hidden />
                health={status.health.rollup} (ops · not authority)
              </span>
              <span>read_plane={status.read_plane}</span>
              <span>edges: derived only</span>
            </div>
            <p className="flags">
              ui_canonical={String(status.ui_canonical)} · unknown_equals_healthy=
              {String(status.unknown_equals_healthy)}
            </p>
          </section>
        ) : null}
      </main>
    </LabShell>
  );
}
