import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useConversationCaptures } from "../../hooks/useConversationCaptures";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * Conversation-capture micro-lens — AS-CODER-ALPHA-CONVERSATION-CAPTURES-READ-001.
 * LIVE_API quarantine visibility only; demo never fabricates EMPTY or HEALTHY.
 */
export default function ConversationCapturesPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { view, error, loading, dataSource } =
    useConversationCaptures(projectId);
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;
  const available = view?.available === true;
  const rollup = view?.status ?? "UNKNOWN";
  const rows = view?.captures ?? [];

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
            Production · Conversation captures ·
            AS-CODER-ALPHA-CONVERSATION-CAPTURES-READ-001
          </p>
          <h1>Conversation captures</h1>
          <p className="lede">
            Read-only quarantined conversation inventory. Captures stay
            non-authoritative; a missing directory stays unknown; an empty
            directory is never healthy.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">capture≠truth-core</span>
            <span className="chip">reviewed≠promoted</span>
            <span className="chip">empty≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="conversation-captures-project">
            Focus project
          </label>
          <select
            id="conversation-captures-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            <option value="">vault-scoped — all quarantined captures</option>
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
          <p className="banner warn">
            Conversation-capture read failed: {error}
          </p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample data · not live capture inventory
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Conversation-capture rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">status={rollup}</span>
            <span className="chip">reason={view?.reason_code ?? "UNKNOWN"}</span>
            <span className="chip">
              captures={String(view?.capture_count ?? 0)}
            </span>
          </p>
          {!available ? (
            <p className="banner warn">
              {view?.reason ?? "unknown — no live conversation-capture evidence"}
            </p>
          ) : (
            <p>
              Inventory status is <strong>{rollup}</strong>. That is a derived
              operational signal, not a claim the captures are Truth Core or
              owner-authorized.
            </p>
          )}
        </section>

        <section className="panel" aria-label="Conversation-capture rows">
          <h2>Quarantined captures</h2>
          {rows.length === 0 ? (
            <p className="banner warn">
              {rollup === "EMPTY"
                ? "directory present and empty for this scope (not a healthy bill)"
                : "UNKNOWN — no conversation-capture evidence"}
            </p>
          ) : (
            <ul>
              {rows.map((row) => (
                <li key={row.capture_id ?? `${row.project_id}:${row.summary}`}>
                  {row.capture_id ?? "UNKNOWN"} · {row.review_state ?? "captured"}{" "}
                  · {row.summary ?? "no summary"}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Conversation-capture boundaries">
          <h2>Boundaries</h2>
          <p className="banner warn">
            UI ≠ canonical — browser state is never vault truth.
          </p>
          <p className="banner warn">
            CAPTURE ≠ TRUTH CORE — quarantined conversation evidence is not
            project authority.
          </p>
          <p className="banner warn">
            REVIEWED ≠ PROMOTED — a review_state change never grants owner
            capability.
          </p>
          <p className="banner warn">
            EMPTY ≠ HEALTHY — an empty directory is not a clean bill of health.
          </p>
          <p className="disclaimer">
            Read-only lens · no capture/write · conversation ≠ owner authority
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
