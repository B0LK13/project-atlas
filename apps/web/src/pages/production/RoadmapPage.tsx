import { ProdShell } from "../../components/ProdShell";
import { useLiveRoadmap } from "../../hooks/useLiveRoadmap";

const DEFAULT_PROJECT = "harbor-api";

/**
 * AS-PROJECT-ROADMAP-001 web lens — derived Living Project Roadmap V1.
 * UI ≠ canonical; ROADMAP ≠ authority; UNKNOWN ≠ healthy.
 */
export default function RoadmapPage() {
  const { roadmap, error, loading, dataSource } = useLiveRoadmap(DEFAULT_PROJECT);
  const isDemo = dataSource === "demo_stub";
  const here = roadmap?.you_are_here;
  const nextUnlock = roadmap?.next_unlock;
  const path = roadmap?.critical_path ?? [];

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Living Project Roadmap V1</p>
          <h1>Project roadmap</h1>
          <p className="lede">
            Derived projection of where <code>{DEFAULT_PROJECT}</code> is, why
            it is there, and what unlocks next. Not canonical truth. Not
            authority. No invented completion percentages.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">roadmap≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Roadmap unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            a live derived roadmap (not vault truth)
          </p>
        ) : null}

        <section className="panel" aria-label="You are here">
          <h2>You are here</h2>
          {!loading && !here ? (
            <p className="banner warn">UNKNOWN — no position evidence</p>
          ) : (
            <p>
              <strong>{here?.title ?? "UNKNOWN"}</strong> [{here?.status ?? "UNKNOWN"}
              {here?.lifecycle ? ` / ${here.lifecycle}` : ""}]
              <span> · {here?.why ?? here?.reason ?? "unknown"}</span>
            </p>
          )}
        </section>

        <section className="panel" aria-label="Next unlock">
          <h2>Next unlock</h2>
          {!nextUnlock ? (
            <p className="banner warn">UNKNOWN — no unlock evidence</p>
          ) : (
            <p>
              <strong>{nextUnlock.title}</strong> [{nextUnlock.status}]
              <span> · {nextUnlock.why ?? nextUnlock.unlock_condition ?? "UNKNOWN"}</span>
            </p>
          )}
        </section>

        <section className="panel" aria-label="Critical path">
          <h2>Critical path</h2>
          {path.length === 0 ? (
            <p className="banner warn">
              {roadmap?.honesty?.cyclic_dependencies
                ? "UNKNOWN — cyclic dependencies; no invented path"
                : "empty — no remaining-work path (not an invented completion)"}
            </p>
          ) : (
            <p>{path.join(" → ")}</p>
          )}
        </section>

        <section className="panel" aria-label="Blockers">
          <h2>Blockers</h2>
          {(roadmap?.blockers ?? []).length === 0 ? (
            <p>No derived blockers on this lens.</p>
          ) : (
            <ul>
              {(roadmap?.blockers ?? []).map((blocker, index) => (
                <li key={`${blocker.waiting_on ?? "none"}-${index}`}>
                  {blocker.reason ?? "UNKNOWN"}
                  {blocker.waiting_on ? ` · waiting on ${blocker.waiting_on}` : ""}
                  {blocker.unlock_condition
                    ? ` · unlock: ${blocker.unlock_condition}`
                    : ""}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Work items">
          <h2>Items</h2>
          {(roadmap?.items ?? []).length === 0 ? (
            <p className="banner warn">UNKNOWN — no roadmap items</p>
          ) : (
            <ul className="theme-hub">
              {(roadmap?.items ?? []).map((item) => (
                <li key={item.id}>
                  <strong>
                    {item.critical_path ? "* " : ""}
                    {item.id}
                  </strong>
                  <span>
                    [{item.status}] {item.title}
                    {item.missing_acceptance_evidence
                      ? " · missing acceptance evidence"
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Unknowns">
          <h2>Unknowns</h2>
          {(roadmap?.unknowns ?? []).length === 0 ? (
            <p>No UNKNOWN signals on this derived lens.</p>
          ) : (
            <ul>
              {(roadmap?.unknowns ?? []).map((unknown) => (
                <li key={unknown}>{unknown}</li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </ProdShell>
  );
}
