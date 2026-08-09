import { useEffect, useState } from "react";
import type { ReadStatus } from "./types";

const STUB_URL = "/sample-read-status.json";

export default function App() {
  const [status, setStatus] = useState<ReadStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(STUB_URL)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`stub HTTP ${response.status}`);
        }
        return (await response.json()) as ReadStatus;
      })
      .then((payload) => {
        if (!cancelled) {
          setStatus(payload);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "stub load failed");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">Project Atlas · AS-WEB-001</p>
        <h1>Atlas</h1>
        <p className="lede">
          Read-first vault status shell. UI is not canonical; graph is not
          authority; unknown is never healthy.
        </p>
      </header>

      {error ? <p className="banner warn">Read status unavailable: {error}</p> : null}
      {!status && !error ? <p className="banner">Loading read status…</p> : null}

      {status ? (
        <section className="panel" aria-label="Vault read status">
          <h2>Vault read status</h2>
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
              <dd className={status.health.rollup === "unknown" ? "unknown" : undefined}>
                {status.health.rollup}
              </dd>
            </div>
            <div>
              <dt>Health source</dt>
              <dd>{status.health.source}</dd>
            </div>
          </dl>
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
        </section>
      ) : null}
    </main>
  );
}
