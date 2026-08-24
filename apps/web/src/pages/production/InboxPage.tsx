import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveInbox } from "../../hooks/useLiveInbox";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-INBOX-WEB-001 — derived Knowledge Inbox list.
 * UI ≠ canonical; INBOX ≠ authority; listing ≠ mutation ≠ command.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function InboxPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { inbox, error, loading, dataSource } = useLiveInbox(projectId);
  const isDemo = dataSource === "demo_stub";
  const items = inbox?.items ?? [];
  const lensProject =
    typeof inbox?.project_id === "string" ? inbox.project_id.trim() : "";
  const projectMismatch = Boolean(
    inbox && projectId && lensProject && lensProject !== projectId,
  );

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
          <p className="eyebrow">Production · Coder Alpha Inbox</p>
          <h1>Inbox</h1>
          <p className="lede">
            Derived knowledge-inbox list for{" "}
            <code>{projectId ?? "UNKNOWN"}</code>. Listing is not a command.
            Listing is not mutation. Inbox is not authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">inbox≠authority</span>
            <span className="chip">listing≠command</span>
            <span className="chip">listing≠mutation</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="inbox-project">
            Focus project
          </label>
          <select
            id="inbox-project"
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

        {error ? <p className="banner warn">Inbox unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            a live derived inbox list (not vault truth)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — inbox project does not match selected project
          </p>
        ) : null}

        <section className="panel" aria-label="Inbox rows">
          <h2>Items</h2>
          {!loading && !inbox ? (
            <p className="banner warn">UNKNOWN — no inbox evidence</p>
          ) : null}
          {inbox?.unknown ? <p className="banner warn">{inbox.unknown}</p> : null}
          {items.length === 0 ? (
            <p className="banner warn">UNKNOWN — no inbox item rows</p>
          ) : (
            <ul>
              {items.map((item) => (
                <li key={item.receipt_id ?? item.summary}>
                  [{item.status ?? "UNKNOWN"}] {item.summary ?? "UNKNOWN"}
                  <span> · {item.receipt_id ?? "unknown"}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="lede">These rows are observations, not commands.</p>
        </section>
      </main>
    </ProdShell>
  );
}
