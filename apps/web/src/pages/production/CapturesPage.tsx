import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveCaptures } from "../../hooks/useLiveCaptures";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-CAPTURE-LIST-001 web lens — session-capture inventory.
 * UI ≠ canonical; captures are ops receipts, not Layer B authority.
 */
export default function CapturesPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { inventory, error, loading, dataSource } = useLiveCaptures(projectId);
  const isDemo = dataSource === "demo_stub" || inventory?.demo_isolated === true;
  const rows = inventory?.captures ?? [];
  const available = inventory?.available === true;

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
          <p className="eyebrow">
            Production · Session captures · AS-CODER-ALPHA-CAPTURE-LIST-001
          </p>
          <h1>Session captures</h1>
          <p className="lede">
            Read-only inventory of session-memory receipts. Captures are ops
            evidence, not Truth Core. Empty lists stay unknown; the browser
            never invents milestones or authentic PILOT.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">capture≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Capture read failed: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample data · not live vault
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Project filter">
          <h2>Project filter</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="captures-project">
            Optional project scope
          </label>
          <select
            id="captures-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            <option value="">all projects in this vault</option>
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

        <section className="panel" aria-label="Capture inventory">
          <h2>Inventory</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">
              capture_count={inventory?.capture_count ?? 0}
            </span>
            <span className="chip">
              authentic_pilot=
              {String(inventory?.honesty?.authentic_pilot ?? false)}
            </span>
          </p>
          {!available ? (
            <p className="banner warn">unknown — capture list unavailable</p>
          ) : rows.length === 0 ? (
            <p className="banner warn">
              UNKNOWN — no session captures yet; run atlas capture record
            </p>
          ) : (
            <ul>
              {rows.map((row) => (
                <li key={row.capture_id ?? row.path}>
                  <strong>
                    [{row.kind ?? "note"}] {row.summary ?? "UNKNOWN"}
                  </strong>
                  <span>
                    {" "}
                    ({row.project_id ?? "UNKNOWN"} · {row.capture_id ?? "UNKNOWN"})
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="disclaimer">
            Unknown ≠ healthy · UI ≠ canonical · session capture ≠ Layer B
            {isDemo ? " · demo isolated" : ""}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
