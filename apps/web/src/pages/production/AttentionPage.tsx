import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveAttention } from "../../hooks/useLiveAttention";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-ATTENTION-WEB-001 — derived attention hygiene lens.
 * UI ≠ canonical; ATTENTION ≠ authority; CLEAR requires inspection.
 * Distinct from intelligence /v1/project-attention.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function AttentionPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { attention, error, loading, dataSource } = useLiveAttention(projectId);
  const isDemo = dataSource === "demo_stub";
  const care = attention?.care_about ?? [];
  const items = attention?.items ?? [];
  const lensProject =
    typeof attention?.project_id === "string" ? attention.project_id.trim() : "";
  const projectMismatch = Boolean(
    attention && projectId && lensProject && lensProject !== projectId,
  );
  const rollup = attention?.rollup ?? "unknown";

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
          <p className="eyebrow">Production · Coder Alpha Attention</p>
          <h1>Attention</h1>
          <p className="lede">
            Derived attention hygiene for{" "}
            <code>{projectId ?? "UNKNOWN"}</code>. Attention is not authority.
            Clear requires positive inspection. This is not project-attention.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">attention≠authority</span>
            <span className="chip">clear≠default</span>
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

        {error ? (
          <p className="banner warn">Attention unavailable: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            a live derived attention lens (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — attention project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Attention rollup">
          <h2>Care about</h2>
          {!loading && !attention ? (
            <p className="banner warn">UNKNOWN — no attention evidence</p>
          ) : null}
          {attention ? (
            <p className="lede">
              rollup=[{rollup}] · items={String(attention.item_count ?? "unknown")}
            </p>
          ) : null}
          {rollup === "unknown" || rollup === "UNKNOWN" ? (
            <p className="banner warn">UNKNOWN — attention is not CLEAR by default</p>
          ) : null}
          {care.length === 0 ? (
            <p className="banner warn">UNKNOWN — no care-about rows</p>
          ) : (
            <ul>
              {care.map((item) => (
                <li key={`${item.level}-${item.reason_code}-${item.subject_id}`}>
                  [{item.level ?? "UNKNOWN"}] {item.why_seeing_this ?? "UNKNOWN"}
                  <span> · {item.what_to_do ?? "unknown"}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="lede">These rows are observations, not commands.</p>
          {items.length > 0 ? (
            <p className="lede">
              Full item rows remain derived evidence ({items.length}), not
              owner grants.
            </p>
          ) : null}
        </section>
      </main>
    </ProdShell>
  );
}
