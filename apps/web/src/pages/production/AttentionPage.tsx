import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveProjectAttention } from "../../hooks/useLiveProjectAttention";
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

/**
 * AS-CODER-ALPHA-STATE-ATTENTION-WEB-MCP-001 — first-class Attention page.
 * UI ≠ canonical. Attention is not a score. Empty is UNKNOWN, never healthy.
 */
export default function AttentionPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { attention, error, loading, dataSource } =
    useLiveProjectAttention(projectId);
  const isDemo = dataSource === "demo_stub";
  const lensProject = text(attention?.project_id ?? attention?.project, "");
  const projectMismatch = Boolean(
    attention && projectId && lensProject && lensProject !== projectId,
  );

  function onSelectProject(next: string) {
    const nextParams = new URLSearchParams(params);
    if (next) {
      nextParams.set("project", next);
    } else {
      nextParams.delete("project");
    }
    setParams(nextParams, { replace: true });
  }

  const risks = asList(attention?.risks);
  const honesty = text(attention?.honesty, "UNKNOWN");

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Coder Alpha Attention</p>
          <h1>Attention</h1>
          <p className="lede">
            Derived attention hygiene for <code>{projectId ?? "UNKNOWN"}</code>.
            Not a score. Not a health grade. Risk is not fact.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">attention≠score</span>
            <span className="chip">risk≠fact</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="attention-project">
            Focus project
          </label>
          <select
            id="attention-project"
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

        {error ? <p className="banner warn">Attention unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            live derived attention (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — attention project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Honesty">
          <h2>Honesty</h2>
          <p>
            <span className="chip">{honesty}</span>
            <span className="chip">
              rank_is_score={text(attention?.attention_rank_is_score, "NO")}
            </span>
            <span className="chip">{text(attention?.authority_note, "risk-is-not-fact")}</span>
          </p>
        </section>

        <section className="panel" aria-label="Attention signals">
          <h2>Signals</h2>
          {risks.length === 0 ? (
            <p className="banner warn">UNKNOWN — no attention signals. Not healthy.</p>
          ) : (
            <ul className="theme-hub">
              {risks.map((item, index) => (
                <li key={text(item.signal_id ?? item.risk_id ?? item.attention_id, `risk-${index}`)}>
                  <strong>{text(item.risk_class ?? item.kind)}</strong>
                  <span> · {text(item.reason)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </ProdShell>
  );
}
