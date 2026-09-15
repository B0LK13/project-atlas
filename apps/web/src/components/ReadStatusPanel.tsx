import type { ReadStatus } from "../types";

interface ReadStatusPanelProps {
  status: ReadStatus;
  compact?: boolean;
}

/** Shared read-status fields — LIVE labelled; demo stub isolated; never canonical. */
export function ReadStatusPanel({ status, compact = false }: ReadStatusPanelProps) {
  const source = status.data_source ?? (status.read_plane === "stub" ? "demo_stub" : "live_api");
  const isDemo = source === "demo_stub" || status.demo_isolated === true;
  return (
    <section
      className="panel"
      aria-label={isDemo ? "Vault read status (demo stub)" : "Vault read status (live API)"}
    >
      <h2>Vault read status</h2>
      <p className={isDemo ? "banner warn" : "banner"}>
        {isDemo
          ? "DEMO STUB — isolated sample data · not live vault · not acceptance"
          : "LIVE_API — read-only vault projection · UI ≠ canonical"}
      </p>
      <p className="disclaimer">
        UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy
        {isDemo ? " · demo isolated from LIVE_API" : ""}
      </p>
      <dl className="grid">
        <div>
          <dt>Data source</dt>
          <dd>{source}</dd>
        </div>
        <div>
          <dt>Vault</dt>
          <dd>{status.vault_present ? status.vault_id ?? "present" : "absent"}</dd>
        </div>
        <div>
          <dt>Read plane</dt>
          <dd>{status.read_plane}</dd>
        </div>
        <div>
          <dt>Health rollup</dt>
          <dd className={status.health.rollup === "unknown" ? "rollup-unknown" : undefined}>
            {status.health.rollup}
          </dd>
        </div>
        <div>
          <dt>Health source</dt>
          <dd>{status.health.source}</dd>
        </div>
      </dl>
      {!compact ? (
        <>
          <p className="disclaimer">{status.health.disclaimer}</p>
          <p className="flags">
            ui_canonical={String(status.ui_canonical)} · graph_authority=
            {String(status.graph_authority)} · unknown_equals_healthy=
            {String(status.unknown_equals_healthy)} · demo_isolated=
            {String(status.demo_isolated ?? isDemo)}
          </p>
          <h3>Projects (read-only)</h3>
          {status.projects.length === 0 ? (
            <p className="empty">No projects listed (honest empty).</p>
          ) : (
            <ul>
              {status.projects.map((project) => (
                <li key={project.project_id}>
                  <code>{project.project_id}</code>
                  {project.has_project_note ? " · project.md" : " · no project.md"}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </section>
  );
}
