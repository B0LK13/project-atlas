import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AuthorityMark, TruthBadge, WorkflowBadge } from "./StatusLanguage";

describe("non-color state language", () => {
  it.each(["OBSERVED", "DERIVED", "INFERRED", "SIMULATED", "UNKNOWN", "CONTESTED", "STALE"] as const)(
    "renders the %s truth label with a glyph",
    (state) => {
      const markup = renderToStaticMarkup(<TruthBadge state={state} />);
      expect(markup).toContain(state);
      expect(markup).toContain("<svg");
    },
  );

  it("keeps workflow separate from truth language", () => {
    const markup = renderToStaticMarkup(<WorkflowBadge state="WAITING_FOR_IV" />);
    expect(markup).toContain("WAITING FOR IV");
    expect(markup).toContain("workflow-waiting-for-iv");
  });

  it("does not equate agent existence with authority", () => {
    const markup = renderToStaticMarkup(<AuthorityMark authorized={false} ownsLane={false} />);
    expect(markup).toContain("no authority");
    expect(markup).not.toContain("lane owner");
  });
});
