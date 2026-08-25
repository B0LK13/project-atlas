import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveProjectState } from "../../hooks/useLiveProjectState";
import { useReadStatus } from "../../hooks/useReadStatus";

function asList(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

function text(value: unknown, fallback = "UNKNOWN"): string {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return fallback;
}

function FactList({
  title,
  items,
}: {
  title: string;
  items: Record<string, unknown>[];
}) {
  return (
    <section className="panel" aria-label={title}>
      <h2>{title}</h2>
      {items.length === 0 ? (
        <p className="banner warn">UNKNOWN — no {title.toLowerCase()} on this lens</p>
      ) : (
        <ul className="theme-hub">
          {items.map((item, index) => (
            <li key={text(item.fact_id, `${title}-${index}`)}>
              <strong>{text(item.field)}</strong>
              <span>
                [{text(item.status).toUpperCase()}] {text(item.value ?? item.why)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * AS-CODER-ALPHA-STATE-ATTENTION-WEB-MCP-001 — first-class Current State page.
 * UI ≠ canonical. Derived state ≠ authority. Empty is UNKNOWN, never healthy.
 */
export default function StatePage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { state, error, loading, dataSource } = useLiveProjectState(projectId);
  const isDemo = dataSource === "demo_stub";
  const lensProject = text(state?.project_id ?? state?.project, "");
  const projectMismatch = Boolean(state && projectId && lensProject && lensProject !== projectId);

  function onSelectProject(next: string) {
    const nextParams = new URLSearchParams(params);
    if (next) {
      nextParams.set("project", next);
    } else {
      nextParams.delete("project");
    }
    setParams(nextParams, { replace: true });
  }

  const honesty = text(state?.honesty, "UNKNOWN");
  const known = asList(state?.known_facts);
  const unknown = asList(state?.unknown_facts);
  const stale = asList(state?.stale_facts);
  const contested = asList(state?.contested_facts);

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Coder Alpha Current State</p>
          <h1>Project state</h1>
          <p className="lede">
            Derived current-state lens for <code>{projectId ?? "UNKNOWN"}</code>.
            Not canonical truth. Not a health grade. UNKNOWN is valid.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">state≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="state-project">
            Focus project
          </label>
          <select
            id="state-project"
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

        {error ? <p className="banner warn">State unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            live derived state (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — state project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Honesty">
          <h2>Honesty</h2>
          <p>
            <span className="chip">{honesty}</span>
            <span className="chip">{text(state?.authority_note, "derived-state-not-canonical")}</span>
          </p>
          <p className="lede">{text(state?.reason ?? state?.why, "derived-state-not-canonical")}</p>
        </section>

        <FactList title="Known facts" items={known} />
        <FactList title="Unknown facts" items={unknown} />
        <FactList title="Stale facts" items={stale} />
        <FactList title="Contested facts" items={contested} />
      </main>
    </ProdShell>
  );
}
