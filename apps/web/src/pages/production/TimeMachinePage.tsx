import { ProdShell } from "../../components/ProdShell";
import {
  TIME_MACHINE_PROJECT,
  TIME_MACHINE_T1,
  TIME_MACHINE_T2,
  useLiveTimeMachine,
  type KdiffCell,
} from "../../hooks/useLiveTimeMachine";

/**
 * AS-2.2-KDIFF-001 web lens — conflict + Time Machine (as-of / T1→T2 diff)
 * for the fixed golden demo scope (harbor-api). LIVE_API preferred; demo
 * fallback stays empty and isolated. Read-only; kdiff ≠ authority.
 */
export default function TimeMachinePage() {
  const {
    conflicts,
    asOfT1Cells,
    asOfT2Cells,
    diff,
    error,
    loading,
    dataSource,
  } = useLiveTimeMachine();
  const isDemo = dataSource === "demo_stub";

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Conflict &amp; Time Machine</p>
          <h1>Conflict &amp; Time Machine</h1>
          <p className="lede">
            Read-only view of the <code>{TIME_MACHINE_PROJECT}</code> LIVE state:
            the unresolved conflict plus the Time Machine as-of snapshots at{" "}
            {TIME_MACHINE_T1} and {TIME_MACHINE_T2} and the T1→T2 diff.
            LIVE_API preferred; demo fallback stays empty and isolated — nothing
            is invented in the browser.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">kdiff≠authority</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Time Machine unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            live conflict + Time Machine state (not vault truth)
          </p>
        ) : null}

        <section className="panel" aria-label="Unresolved conflict">
          <h2>Unresolved conflict</h2>
          {!loading && conflicts.length === 0 ? (
            <p className="banner warn">unknown — no conflict rows</p>
          ) : (
            <ul className="theme-hub">
              {conflicts.map((conflict, index) => (
                <li key={conflict.conflict_id || `${conflict.subject}-${index}`}>
                  <strong>
                    {conflict.subject} · {conflict.field}
                  </strong>
                  <span>type: {conflict.conflict_type}</span>
                  <div className="flags" style={{ marginTop: "0.5rem" }}>
                    {conflict.claims.map((claim, claimIndex) => (
                      <span
                        key={`${claim.source_id ?? "unsourced"}-${claimIndex}`}
                        className="chip"
                      >
                        {claimIndex === 0 ? "VALUE A" : claimIndex === 1 ? "VALUE B" : `VALUE ${claimIndex + 1}`}
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
          <p className="disclaimer">
            Conflict projection ≠ authority · ≠ resolution
            {isDemo ? " · demo isolated from LIVE_API" : " · LIVE_API read-only"}
          </p>
        </section>

        <section className="panel" aria-label="Time Machine">
          <h2>Time Machine</h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "1rem",
            }}
          >
            <div>
              <h3>At T1 ({TIME_MACHINE_T1})</h3>
              <AsOfCells cells={asOfT1Cells} loading={loading} />
            </div>
            <div>
              <h3>At T2 ({TIME_MACHINE_T2})</h3>
              <AsOfCells cells={asOfT2Cells} loading={loading} />
            </div>
          </div>

          <h3 style={{ marginTop: "1rem" }}>What changed T1 → T2</h3>
          {!loading &&
          diff.value_changed.length === 0 &&
          diff.added.length === 0 ? (
            <p className="banner warn">unknown — no recorded changes</p>
          ) : (
            <ul className="theme-hub">
              {diff.value_changed.map((change, index) => (
                <li key={`changed-${change.subject}-${change.field}-${index}`}>
                  <strong>
                    {change.subject}.{change.field}
                  </strong>
                  <span>
                    {change.from_value_sketch || "—"} →{" "}
                    {change.to_value_sketch || "—"}
                  </span>
                </li>
              ))}
              {diff.added.map((added, index) => (
                <li key={`added-${added.subject}-${added.field}-${index}`}>
                  <strong>
                    {added.subject}.{added.field}
                  </strong>
                  <span>+ {added.value_sketch ?? "—"} (added)</span>
                </li>
              ))}
            </ul>
          )}
          <p className="disclaimer">
            Time Machine read (as-of / T1→T2) · kdiff ≠ authority
            {isDemo ? " · demo isolated from LIVE_API" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}

function AsOfCells({
  cells,
  loading,
}: {
  cells: KdiffCell[];
  loading: boolean;
}) {
  if (!loading && cells.length === 0) {
    return <p className="banner warn">unknown — no cells</p>;
  }
  return (
    <ul className="theme-hub">
      {cells.map((cell, index) => {
        const absent =
          cell.disposition === "not_found" || cell.disposition === "absent";
        return (
          <li key={`${cell.subject}-${cell.field}-${index}`}>
            <strong>
              {cell.subject} · {cell.field}
            </strong>
            <span style={{ display: "block" }}>
              disposition: {cell.disposition}
            </span>
            <span style={{ display: "block" }}>
              {absent ? "— (absent)" : cell.value_sketch ?? "—"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
