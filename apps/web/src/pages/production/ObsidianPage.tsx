import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveObsidian } from "../../hooks/useLiveObsidian";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-OBSIDIAN-READ-001 web lens — read-only living-note inventory.
 * UI ≠ canonical; PROJECTION ≠ plugin; UNKNOWN ≠ healthy.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function ObsidianPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { inventory, error, loading, dataSource } = useLiveObsidian(projectId);
  const isDemo = dataSource === "demo_stub";
  const rows = inventory?.notes ?? [];
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
          <p className="eyebrow">Production · Obsidian living notes</p>
          <h1>Obsidian</h1>
          <p className="lede">
            Read-only inventory of existing{" "}
            <code>generated/obsidian/projects/</code> living notes for{" "}
            <code>{projectId ?? "the vault"}</code>. This page does not
            materialize or rewrite notes. Not a plugin. Not canonical. Not
            authority. Empty is UNKNOWN, not a healthy zero.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">projection≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">materialize_or_write=false</span>
            <span className="chip">plugin_shipped=false</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="obsidian-project">
            Focus project
          </label>
          <select
            id="obsidian-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            <option value="">all vault living notes</option>
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

        {error ? <p className="banner warn">Obsidian unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to
            read live living notes (not invented)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — living-note project does not match selected project
          </p>
        ) : null}
        {!loading && !error && !isDemo && !projectMismatch && rows.length === 0 ? (
          <p className="banner warn">
            UNKNOWN — no living notes. Run <code>atlas obsidian project</code>.
            Empty is not a healthy zero.
          </p>
        ) : null}

        {!projectMismatch && rows.length > 0 ? (
          <section className="panel" aria-label="Living-note inventory">
            <h2>Existing notes</h2>
            <p className="lede">count={inventory?.note_count ?? 0}</p>
            <ul>
              {rows.map((row) => (
                <li key={`${row.project_id}-${row.path}`}>
                  <strong>{row.project_id ?? "UNKNOWN"}</strong>
                  {row.has_human_notes ? " · human notes present" : ""}
                  {row.has_generated_markers ? " · generated markers" : ""}
                  <div className="lede">
                    path=<code>{row.path ?? "UNKNOWN"}</code>
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
