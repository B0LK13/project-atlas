import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveConflicts } from "../../hooks/useLiveConflicts";

/**
 * Vault-scoped unresolved conflict index — projection ≠ resolution.
 * LIVE_API preferred; demo fallback stays unknown (never fabricated winners).
 */
export default function ConflictsPage() {
  const [params] = useSearchParams();
  const projectFilter = (params.get("project") || "").trim();
  const { index, error, loading, dataSource } = useLiveConflicts();
  const isDemo = dataSource === "demo_stub";
  const rows = (index?.projects ?? []).filter((row) =>
    projectFilter ? row.project_id === projectFilter : true,
  );
  const liveReady = dataSource === "live_api";

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Conflicts · AS-CODER-ALPHA-CONFLICTS-MCP-001</p>
          <h1>Conflicts</h1>
          <p className="lede">
            Vault-scoped unresolved conflict projection. Atlas never picks a
            winner. UI is not canonical and a readable estate is not owner
            authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">conflict≠resolution</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Conflicts unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            live conflict rows (not vault truth)
          </p>
        ) : liveReady ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Unresolved conflicts">
          <h2>Unresolved conflicts</h2>
          <p className="flags">
            <span className="chip">
              projects={String(index?.project_count ?? "unknown")}
            </span>
            <span className="chip">
              conflicts={String(index?.conflict_count ?? "unknown")}
            </span>
            {projectFilter ? (
              <span className="chip">filter={projectFilter}</span>
            ) : null}
          </p>
          {liveReady && rows.length === 0 ? (
            <p className="banner warn">unknown — no conflict project rows</p>
          ) : !liveReady && rows.length === 0 ? (
            <p className="lede">
              {error
                ? "Unavailable — not an empty conflict catalog."
                : isDemo
                  ? "Demo stub isolated — not an empty conflict catalog."
                  : "Waiting for live conflict rows."}
            </p>
          ) : (
            rows.map((project) => (
              <article key={project.project_id || "unknown-project"}>
                <h3>{project.project_id || "UNKNOWN"}</h3>
                {(project.conflicts ?? []).length === 0 ? (
                  <p className="banner">No unresolved conflicts recorded</p>
                ) : (
                  <ul className="theme-hub">
                    {(project.conflicts ?? []).map((conflict, indexRow) => (
                      <li
                        key={
                          conflict.conflict_id ||
                          `${conflict.subject}-${conflict.field}-${indexRow}`
                        }
                      >
                        <strong>
                          {conflict.subject} · {conflict.field}
                        </strong>
                        <span>type: {conflict.conflict_type || "unknown"}</span>
                        <div className="flags" style={{ marginTop: "0.5rem" }}>
                          {(conflict.claims ?? []).map((claim, claimIndex) => (
                            <span
                              key={`${claim.source_id ?? "unsourced"}-${claimIndex}`}
                              className="chip"
                            >
                              {claimIndex === 0
                                ? "VALUE A"
                                : claimIndex === 1
                                  ? "VALUE B"
                                  : `VALUE ${claimIndex + 1}`}
                              : {claim.claim || "—"} (source:{" "}
                              {claim.source_id ?? "—"})
                            </span>
                          ))}
                        </div>
                        <span style={{ marginTop: "0.5rem" }}>
                          UNRESOLVED — Atlas does not pick a winner
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            ))
          )}
          <p className="disclaimer">
            Conflict projection ≠ authority · ≠ resolution · UI ≠ canonical
            {isDemo ? " · demo isolated from LIVE_API" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
