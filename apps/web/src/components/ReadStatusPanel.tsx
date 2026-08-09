import type { ReadStatus } from "../types";

interface ReadStatusPanelProps {
  status: ReadStatus;
  compact?: boolean;
}

/** Shared sample/read-status fields — never elevates UI to canonical. */
export function ReadStatusPanel({ status, compact = false }: ReadStatusPanelProps) {
  return (
    <section className="panel" aria-label="Vault read status (sample)">
      <h2>Vault read status</h2>
      <p className="disclaimer">Sample / stub only — not production acceptance.</p>
      <dl className="grid">
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
            {String(status.unknown_equals_healthy)}
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
