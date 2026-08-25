import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useInventoryDrift } from "../../hooks/useInventoryDrift";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * Inventory-drift micro-lens — AS-CODER-ALPHA-INVENTORY-DRIFT-READ-001.
 * LIVE_API freshness only; demo never fabricates FRESH.
 */
export default function InventoryDriftPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { view, error, loading, dataSource } = useInventoryDrift(projectId);
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;
  const available = view?.available === true;
  const rollup = view?.status ?? "UNKNOWN";
  const changed = view?.changed_paths ?? [];
  const rows = view?.projects ?? [];

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
            Production · Inventory drift · AS-CODER-ALPHA-INVENTORY-DRIFT-READ-001
          </p>
          <h1>Inventory drift</h1>
          <p className="lede">
            Read-only connect-inventory freshness. A missing manifest stays
            unknown; stale live files are never current; this page is not
            Truth Core authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">stale≠current</span>
            <span className="chip">unknown≠fresh</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="inventory-drift-project">
            Focus project
          </label>
          <select
            id="inventory-drift-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            <option value="">vault-scoped — all real owners</option>
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
          <p className="banner warn">Inventory-drift read failed: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample data · not live inventory freshness
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Inventory-drift rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">status={rollup}</span>
            <span className="chip">reason={view?.reason_code ?? "UNKNOWN"}</span>
            <span className="chip">
              projects={String(view?.project_count ?? (projectId ? 1 : 0))}
            </span>
          </p>
          {!available ? (
            <p className="banner warn">
              {view?.reason ?? "unknown — no live inventory evidence"}
            </p>
          ) : (
            <p>
              Inventory status is <strong>{rollup}</strong>. That is a derived
              freshness signal, not a claim the vault is authoritative or
              validated.
            </p>
          )}
        </section>

        <section className="panel" aria-label="Changed paths">
          <h2>Changed paths</h2>
          {changed.length === 0 && rows.every((row) => !row.changed_paths?.length) ? (
            <p className="banner warn">
              {rollup === "FRESH"
                ? "no drifted paths on this derived lens (not an invented clean bill)"
                : "UNKNOWN — no changed-path evidence"}
            </p>
          ) : (
            <ul>
              {changed.map((path) => (
                <li key={path}>{path}</li>
              ))}
              {rows.flatMap((row) =>
                (row.changed_paths ?? []).map((path) => (
                  <li key={`${row.project_id ?? "unknown"}:${path}`}>
                    {row.project_id ?? "UNKNOWN"} · {path}
                  </li>
                )),
              )}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Inventory-drift boundaries">
          <h2>Boundaries</h2>
          <p className="banner warn">
            UI ≠ canonical — browser state is never vault truth.
          </p>
          <p className="banner warn">
            UNKNOWN ≠ FRESH — a missing inventory never looks current.
          </p>
          <p className="banner warn">
            STALE ≠ CURRENT — drifted sources are not owner authority.
          </p>
          <p className="disclaimer">
            Read-only lens · no connect/write · inventory drift ≠ owner
            authority
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
