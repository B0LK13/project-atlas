import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useEventTombstones } from "../../hooks/useEventTombstones";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * Event-tombstone micro-lens — AS-CODER-ALPHA-EVENT-TOMBSTONES-READ-001.
 * LIVE_API deletion visibility only; demo never fabricates EMPTY or HEALTHY.
 */
export default function EventTombstonesPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { view, error, loading, dataSource } = useEventTombstones(projectId);
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;
  const available = view?.available === true;
  const rollup = view?.status ?? "UNKNOWN";
  const rows = view?.tombstones ?? [];

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
            Production · Event tombstones · AS-CODER-ALPHA-EVENT-TOMBSTONES-READ-001
          </p>
          <h1>Event tombstones</h1>
          <p className="lede">
            Read-only deletion inventory. Removed agent-event units stay visible;
            a missing index stays unknown; an empty index is never healthy.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">deleted≠vanished</span>
            <span className="chip">empty≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="event-tombstones-project">
            Focus project
          </label>
          <select
            id="event-tombstones-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            <option value="">vault-scoped — all recorded deletions</option>
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
          <p className="banner warn">Event-tombstone read failed: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample data · not live deletion inventory
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Event-tombstone rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">status={rollup}</span>
            <span className="chip">reason={view?.reason_code ?? "UNKNOWN"}</span>
            <span className="chip">
              deleted={String(view?.deleted_count ?? 0)}
            </span>
          </p>
          {!available ? (
            <p className="banner warn">
              {view?.reason ?? "unknown — no live tombstone evidence"}
            </p>
          ) : (
            <p>
              Inventory status is <strong>{rollup}</strong>. That is a derived
              operational signal, not a claim the vault is healthy or
              authoritative.
            </p>
          )}
        </section>

        <section className="panel" aria-label="Tombstone rows">
          <h2>Removed units</h2>
          {rows.length === 0 ? (
            <p className="banner warn">
              {rollup === "EMPTY"
                ? "index present and empty for this scope (not a healthy bill)"
                : "UNKNOWN — no tombstone evidence"}
            </p>
          ) : (
            <ul>
              {rows.map((row) => (
                <li key={row.unit_key ?? `${row.project_id}:${row.event_id}`}>
                  {row.unit_key ?? "UNKNOWN"} · {row.reason ?? "unknown"} ·{" "}
                  {row.state ?? "deleted"}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Event-tombstone boundaries">
          <h2>Boundaries</h2>
          <p className="banner warn">
            UI ≠ canonical — browser state is never vault truth.
          </p>
          <p className="banner warn">
            DELETED ≠ VANISHED — removals stay visible as operational tombstones.
          </p>
          <p className="banner warn">
            EMPTY ≠ HEALTHY — an empty index is not a clean bill of health.
          </p>
          <p className="disclaimer">
            Read-only lens · no retention/write · tombstone ≠ owner authority
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
