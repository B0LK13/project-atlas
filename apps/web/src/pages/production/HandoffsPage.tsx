import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveHandoffs } from "../../hooks/useLiveHandoffs";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-HANDOFF-MCP-001 web lens — read-only handoff inventory.
 * UI ≠ canonical; HANDOFF ≠ authority; UNKNOWN ≠ healthy.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function HandoffsPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { inventory, error, loading, dataSource } = useLiveHandoffs(projectId);
  const isDemo = dataSource === "demo_stub";
  const rows = inventory?.handoffs ?? [];
  const inventoryProject =
    typeof inventory?.project_id === "string" ? inventory.project_id.trim() : "";
  const projectMismatch = Boolean(
    inventory && projectId && inventoryProject && inventoryProject !== projectId,
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

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Agent handoffs</p>
          <h1>Handoffs</h1>
          <p className="lede">
            Read-only inventory of durable{" "}
            <code>atlas handoff create</code> packs for{" "}
            <code>{projectId ?? "the vault"}</code>. This page does not create
            or resume a handoff. Not canonical. Not authority. Empty is UNKNOWN,
            not a healthy zero.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">handoff≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">create_or_resume=false</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="handoff-project">
            Focus project
          </label>
          <select
            id="handoff-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            <option value="">all vault handoffs</option>
            {projects.map((project) => (
              <option
                key={project.project_id ?? project.path}
                value={project.project_id ?? ""}
              >
                {project.project_id ?? "unnamed"}
              </option>
            ))}
          </select>
        </section>

        {error ? <p className="banner warn">Handoffs unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to
            read live handoff packs (not invented)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — handoff project does not match selected project
          </p>
        ) : null}
        {!loading && !error && !isDemo && !projectMismatch && rows.length === 0 ? (
          <p className="banner warn">
            UNKNOWN — no handoff packs. Run <code>atlas handoff create</code>.
            Empty is not a healthy zero.
          </p>
        ) : null}

        {!projectMismatch && rows.length > 0 ? (
          <section className="panel" aria-label="Handoff inventory">
            <h2>Stored packs</h2>
            <p className="lede">
              count={inventory?.handoff_count ?? 0}
              {inventory?.latest?.handoff_id
                ? ` · latest=${inventory.latest.handoff_id}`
                : ""}
            </p>
            <ul>
              {rows.map((row) => (
                <li key={`${row.project_id}-${row.handoff_id}`}>
                  <strong>{row.handoff_id ?? "UNKNOWN"}</strong>
                  {" · "}
                  {row.project_id ?? "UNKNOWN"}
                  {" · "}
                  {row.purpose ?? "UNKNOWN"}
                  {row.latest ? " · latest" : ""}
                  <div className="lede">
                    path=<code>{row.path ?? "UNKNOWN"}</code>
                    {row.operator_note ? ` · note=${row.operator_note}` : ""}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </main>
    </ProdShell>
  );
}
