import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveConversationCaptures } from "../../hooks/useLiveConversationCaptures";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-CONVERSATION-CAPTURE-MCP-001 web lens.
 * UI ≠ canonical; CAPTURE ≠ Truth Core; UNKNOWN ≠ healthy.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function ConversationCapturesPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { inventory, error, loading, dataSource } =
    useLiveConversationCaptures(projectId);
  const isDemo = dataSource === "demo_stub";
  const rows = inventory?.captures ?? [];
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
          <p className="eyebrow">Production · Conversation captures</p>
          <h1>Conversation captures</h1>
          <p className="lede">
            Read-only inventory of quarantined conversation-capture receipts
            for <code>{projectId ?? "the vault"}</code>. This page does not
            submit or review captures. Not Truth Core. Not authority. Empty is
            UNKNOWN, not a healthy zero.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">capture≠truth-core</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">submit_or_review=false</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="conversation-project">
            Focus project
          </label>
          <select
            id="conversation-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            <option value="">all vault conversation captures</option>
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

        {error ? (
          <p className="banner warn">Conversation captures unavailable: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to
            read live conversation captures (not invented)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — capture project does not match selected project
          </p>
        ) : null}
        {!loading && !error && !isDemo && !projectMismatch && rows.length === 0 ? (
          <p className="banner warn">
            UNKNOWN — no conversation captures. Empty is not a healthy zero.
          </p>
        ) : null}

        {!projectMismatch && rows.length > 0 ? (
          <section className="panel" aria-label="Conversation-capture inventory">
            <h2>Quarantined receipts</h2>
            <p className="lede">count={inventory?.capture_count ?? 0}</p>
            <ul>
              {rows.map((row) => (
                <li key={`${row.project_id}-${row.capture_id}`}>
                  <strong>{row.capture_id ?? "UNKNOWN"}</strong>
                  {" · "}
                  {row.project_id ?? "UNKNOWN"}
                  {" · "}
                  {row.review_state ?? "captured"}
                  <div className="lede">{row.summary ?? "UNKNOWN"}</div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </main>
    </ProdShell>
  );
}
