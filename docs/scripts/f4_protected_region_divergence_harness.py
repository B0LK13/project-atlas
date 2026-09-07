"""F4 evidence harness: canonical protected-region semantics vs graph projections.

Deterministic, seeded, reconstructible. Generates random HUMAN-region document
shapes, runs each through BOTH merge implementations, and counts:

  * accepted / refused (fail-closed) per implementation
  * HUMAN payload loss among ACCEPTED cases (a payload present in ``existing``
    that does not appear in the merge output)
  * cross-scope substitution (a payload that survives but under a different
    RegionPath than it occupied in ``existing``)

Loss is only counted for ACCEPTED merges: a refusal is fail-closed and
preserves the file, so it is not data loss.

Usage:  python f4_protected_region_divergence_harness.py [--trials N] [--seed S]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys

GEN_START = "<!-- atlas:generated:start -->"
GEN_END = "<!-- atlas:generated:end -->"

NAMES = ("x", "y", "z")


class Region:
    def __init__(self, name: str, payload: str) -> None:
        self.name = name
        self.payload = payload
        self.children: list[Region] = []


def build_tree(rng: random.Random, counter: list[int], depth: int) -> list[Region]:
    """Random forest of HUMAN regions, names drawn from a small colliding set."""
    out: list[Region] = []
    for _ in range(rng.randint(0, 3)):
        counter[0] += 1
        r = Region(rng.choice(NAMES), f"PAYLOAD-{counter[0]:04d}")
        if depth < 2 and rng.random() < 0.45:
            r.children = build_tree(rng, counter, depth + 1)
        out.append(r)
    return out


def render_region(r: Region, *, with_payload: bool) -> str:
    inner = "".join(render_region(c, with_payload=with_payload) for c in r.children)
    body = f"{r.payload}\n" if with_payload else ""
    return (
        f"<!-- BEGIN HUMAN: {r.name} -->\n{body}{inner}"
        f"<!-- END HUMAN: {r.name} -->\n"
    )


def render_doc(forest: list[Region], *, with_payload: bool, gen_body: str) -> str:
    regions = "".join(render_region(r, with_payload=with_payload) for r in forest)
    return f"{GEN_START}\n{gen_body}\n{GEN_END}\n\n{regions}"


def payload_paths(forest: list[Region], prefix: tuple[str, ...] = ()) -> dict[str, tuple[str, ...]]:
    """payload token -> the RegionPath it occupies in the source document."""
    out: dict[str, tuple[str, ...]] = {}
    for r in forest:
        path = (*prefix, r.name)
        out[r.payload] = path
        out.update(payload_paths(r.children, path))
    return out


_TOKEN = re.compile(r"<!--\s*(BEGIN|END) HUMAN:\s*([^\s>]+)\s*-->")


class _Malformed:
    """Sentinel: the document's marker structure does not pair.

    Distinct from ``None`` (payload absent) so a caller cannot silently treat
    a structurally broken document as "payload found at some path".
    """

    __slots__ = ("reason",)

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"MALFORMED({self.reason})"


ABSENT = None


def observed_path(text: str, payload: str) -> tuple[str, ...] | _Malformed | None:
    """RegionPath of ``payload`` in ``text``, by strict structural pairing.

    ``BEGIN name`` pushes; ``END name`` must match the current stack top or the
    document is malformed. An earlier version popped on *any* END, which could
    pop the wrong scope, invent a path for a crossed document, and so miscount
    cross-scope substitution. It now refuses to guess.

    Returns the path, ``None`` if the payload is absent, or a ``_Malformed``
    sentinel naming the first structural fault -- never a fabricated path. The
    whole document is walked even when the payload is found early, so a fault
    *after* the payload still classifies the document as malformed.
    """
    idx = text.find(payload)
    stack: list[str] = []
    found: tuple[str, ...] | None = None
    for m in _TOKEN.finditer(text):
        if idx >= 0 and found is None and m.start() > idx:
            found = tuple(stack)
        if m.group(1) == "BEGIN":
            stack.append(m.group(2))
            continue
        name = m.group(2)
        if not stack:
            return _Malformed(f"orphan-end:{name}")
        if stack[-1] != name:
            return _Malformed(f"unpaired:{name}-closes-{stack[-1]}")
        stack.pop()
    if stack:
        return _Malformed(f"unclosed:{stack[-1]}")
    if idx < 0:
        return ABSENT
    return found if found is not None else tuple(stack)


def _self_test_observed_path() -> None:
    """Assertions for the structural shapes the parser must not fudge."""
    ok = "<!-- BEGIN HUMAN: a -->\n<!-- BEGIN HUMAN: x -->\nP\n" \
         "<!-- END HUMAN: x -->\n<!-- END HUMAN: a -->\n"
    assert observed_path(ok, "P") == ("a", "x"), observed_path(ok, "P")
    assert observed_path(ok, "NOPE") is ABSENT

    crossed = "<!-- BEGIN HUMAN: a -->\nP\n<!-- BEGIN HUMAN: b -->\n" \
              "<!-- END HUMAN: a -->\n<!-- END HUMAN: b -->\n"
    assert isinstance(observed_path(crossed, "P"), _Malformed)

    orphan = "<!-- END HUMAN: a -->\nP\n"
    assert isinstance(observed_path(orphan, "P"), _Malformed)

    unclosed = "<!-- BEGIN HUMAN: a -->\nP\n"
    assert isinstance(observed_path(unclosed, "P"), _Malformed)

    extra_end = "<!-- BEGIN HUMAN: a -->\nP\n<!-- END HUMAN: a -->\n" \
                "<!-- END HUMAN: a -->\n"
    assert isinstance(observed_path(extra_end, "P"), _Malformed)

    # A fault after the payload must still be caught.
    late = "<!-- BEGIN HUMAN: a -->\nP\n<!-- END HUMAN: a -->\n<!-- END HUMAN: b -->\n"
    assert isinstance(observed_path(late, "P"), _Malformed)

    # Sibling scopes with the same leaf name are distinct, not malformed.
    sib = "<!-- BEGIN HUMAN: a -->\n<!-- BEGIN HUMAN: x -->\nPA\n" \
          "<!-- END HUMAN: x -->\n<!-- END HUMAN: a -->\n" \
          "<!-- BEGIN HUMAN: b -->\n<!-- BEGIN HUMAN: x -->\nPB\n" \
          "<!-- END HUMAN: x -->\n<!-- END HUMAN: b -->\n"
    assert observed_path(sib, "PA") == ("a", "x")
    assert observed_path(sib, "PB") == ("b", "x")


# --- Minimal named differential cases (the shapes the randomized run finds) ---

_CASE_BODIES: dict[str, tuple[str, list[str]]] = {
    "same-leaf-name-different-scope (a/x + b/x)": (
        "<!-- BEGIN HUMAN: a -->\n<!-- BEGIN HUMAN: x -->\nPAY-A\n"
        "<!-- END HUMAN: x -->\n<!-- END HUMAN: a -->\n"
        "<!-- BEGIN HUMAN: b -->\n<!-- BEGIN HUMAN: x -->\nPAY-B\n"
        "<!-- END HUMAN: x -->\n<!-- END HUMAN: b -->\n",
        ["PAY-A", "PAY-B"],
    ),
    "same-scope duplicate root (x + x)": (
        "<!-- BEGIN HUMAN: x -->\nPAY-1\n<!-- END HUMAN: x -->\n"
        "<!-- BEGIN HUMAN: x -->\nPAY-2\n<!-- END HUMAN: x -->\n",
        ["PAY-1", "PAY-2"],
    ),
    "same-scope duplicate nested (c/(x + x))": (
        "<!-- BEGIN HUMAN: c -->\n"
        "<!-- BEGIN HUMAN: x -->\nPAY-1\n<!-- END HUMAN: x -->\n"
        "<!-- BEGIN HUMAN: x -->\nPAY-2\n<!-- END HUMAN: x -->\n"
        "<!-- END HUMAN: c -->\n",
        ["PAY-1", "PAY-2"],
    ),
    "self nesting (x inside x)": (
        "<!-- BEGIN HUMAN: x -->\nPAY-OUT\n<!-- BEGIN HUMAN: x -->\nPAY-IN\n"
        "<!-- END HUMAN: x -->\n<!-- END HUMAN: x -->\n",
        ["PAY-OUT", "PAY-IN"],
    ),
    "crossed markers (a b /a /b)": (
        "<!-- BEGIN HUMAN: a -->\nPAY-A\n<!-- BEGIN HUMAN: b -->\nPAY-B\n"
        "<!-- END HUMAN: a -->\n<!-- END HUMAN: b -->\n",
        ["PAY-A", "PAY-B"],
    ),
    "unclosed marker": ("<!-- BEGIN HUMAN: a -->\nPAY-A\n", ["PAY-A"]),
    "nested distinct names (a/b)": (
        "<!-- BEGIN HUMAN: a -->\nPAY-A\n<!-- BEGIN HUMAN: b -->\nPAY-B\n"
        "<!-- END HUMAN: b -->\n<!-- END HUMAN: a -->\n",
        ["PAY-A", "PAY-B"],
    ),
}


def run_named_cases() -> None:
    """Print the canonical-vs-graph verdict for each named shape."""
    from project_atlas import graph_projections, protected_regions

    def _doc(body: str, gen: str) -> str:
        return f"{GEN_START}\n{gen}\n{GEN_END}\n\n{body}"

    print(f"{'case':52} | {'canonical':44} | graph")
    print("-" * 132)
    for name, (body, pays) in _CASE_BODIES.items():
        existing = _doc(body, "OLD generated body")
        rendered = _doc(re.sub(r"(?m)^PAY[-A-Z0-9]*\n", "", body), "NEW generated body")
        row = []
        for fn, err in (
            (protected_regions.merge_protected_regions, protected_regions.ProtectedRegionError),
            (graph_projections._merge_protected_regions, graph_projections.GraphProjectionError),
        ):
            try:
                out = fn(existing=existing, rendered=rendered, path="case.md")
            except err as exc:
                row.append(f"REFUSE {str(exc).split(':')[0]}")
            else:
                lost = [p for p in pays if p not in out]
                row.append(f"ACCEPT lost={lost or 'none'}")
        print(f"{name:52} | {row[0]:44} | {row[1]}")
    print()


# --- Production-path cases: drive the real refresh, not the merge helper ---

_HEALTH_REL = "generated/graph/projections/demo/graph-health.md"
_STUB = "<!-- BEGIN HUMAN: notes -->\n<!-- END HUMAN: notes -->\n"


def run_production_cases() -> None:
    """Seed a real projection, author HUMAN structure into it, refresh once.

    Outcomes differ from the helper-level table because the fresh render only
    carries the default ``notes`` stub, so a human's own regions are appended
    rather than substituted. This is the surface that matters.
    """
    import tempfile
    from pathlib import Path

    from project_atlas.graph_projections import (
        GraphProjectionError,
        materialize_projections,
        write_projection_outputs,
    )

    print(f"{'case':52} | production-path outcome on this tree")
    print("-" * 110)
    for name, (body, pays) in _CASE_BODIES.items():
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            bundle = materialize_projections(project_id="demo")
            write_projection_outputs(bundle, vault=vault)
            path = vault / _HEALTH_REL
            text = path.read_text(encoding="utf-8")
            if _STUB not in text:
                print(f"{name:52} | SKIPPED (projection stub shape changed)")
                continue
            path.write_text(text.replace(_STUB, body), encoding="utf-8")
            try:
                write_projection_outputs(bundle, vault=vault)
            except GraphProjectionError as exc:
                print(f"{name:52} | REFUSE {str(exc).split(':')[0]} (fail-closed)")
                continue
            out = path.read_text(encoding="utf-8")
            lost = [p for p in pays if p not in out]
            dup = [p for p in pays if out.count(p) > 1]
            if lost:
                verdict = f"ACCEPT, drops {lost}"
            elif dup:
                verdict = f"ACCEPT, duplicates {dup}"
            else:
                verdict = "ACCEPT, all payloads preserved"
            print(f"{name:52} | {verdict}")
    _run_reorder_and_refresh_cases()
    print()


def _run_reorder_and_refresh_cases() -> None:
    """Sibling-ordering identity and repeated-refresh stability.

    Held by the harness rather than asserted in prose, so the same command
    that produces every other table also produces these two.
    """
    import tempfile
    from pathlib import Path

    from project_atlas.graph_projections import (
        GraphProjectionError,
        materialize_projections,
        write_projection_outputs,
    )

    two = ("<!-- BEGIN HUMAN: p -->\nPAY-P\n<!-- END HUMAN: p -->\n"
           "<!-- BEGIN HUMAN: q -->\nPAY-Q\n<!-- END HUMAN: q -->\n")

    def _seeded(tmp: str, body: str):
        vault = Path(tmp) / "vault"
        vault.mkdir()
        bundle = materialize_projections(project_id="demo")
        write_projection_outputs(bundle, vault=vault)
        path = vault / _HEALTH_REL
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(_STUB, body), encoding="utf-8")
        return vault, bundle, path

    with tempfile.TemporaryDirectory() as tmp:
        vault, bundle, path = _seeded(tmp, two)
        try:
            write_projection_outputs(bundle, vault=vault)
        except GraphProjectionError as exc:
            print(f"{'sibling reorder, distinct names':52} | REFUSE {exc}")
        else:
            out = path.read_text(encoding="utf-8")
            # Reuse the strict parser rather than a substring scan: an earlier
            # version used rfind, which matched *any* preceding BEGIN of that
            # name (so a payload migrated into a later sibling still read as
            # "no transfer"), and on an absent payload find() returned -1,
            # making rfind scan the whole document and report success for a
            # dropped payload. Both now fail loudly.
            verdict = "no identity transfer"
            for name in ("p", "q"):
                payload = f"PAY-{name.upper()}"
                got = observed_path(out, payload)
                if got is ABSENT:
                    verdict = f"DROPPED {payload}"
                    break
                if isinstance(got, _Malformed):
                    verdict = f"MALFORMED OUTPUT ({got.reason})"
                    break
                if got != (name,):
                    verdict = f"IDENTITY TRANSFER: {payload} at {'/'.join(got) or '(root)'}"
                    break
            print(f"{'sibling reorder, distinct names':52} | {verdict}")

    with tempfile.TemporaryDirectory() as tmp:
        vault, bundle, path = _seeded(tmp, two)
        try:
            write_projection_outputs(bundle, vault=vault)
        except GraphProjectionError as exc:
            print(f"{'repeated refresh (x4)':52} | REFUSE {exc}")
            return
        first = path.read_text(encoding="utf-8")
        for _ in range(3):
            write_projection_outputs(bundle, vault=vault)
        stable = path.read_text(encoding="utf-8") == first
        print(f"{'repeated refresh (x4)':52} | "
              f"{'stable, no accumulation' if stable else 'NOT STABLE'}")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20260907)
    args = ap.parse_args()

    from project_atlas import graph_projections, protected_regions

    _self_test_observed_path()
    run_named_cases()
    run_production_cases()

    stats = {
        impl: {"accepted": 0, "refused": 0, "loss_cases": 0, "lost_payloads": 0,
               "xscope_cases": 0, "dup_cases": 0, "duplicated_payloads": 0,
               "marker_growth_cases": 0, "malformed_output": 0, "error": 0}
        for impl in ("canonical", "graph")
    }
    shapes_with_graph_loss: dict[str, int] = {}

    rng = random.Random(args.seed)
    for _ in range(args.trials):
        counter = [0]
        forest = build_tree(rng, counter, 0)
        if not forest:
            forest = [Region(rng.choice(NAMES), "PAYLOAD-0001")]
        existing = render_doc(forest, with_payload=True, gen_body="old generated body")
        rendered = render_doc(forest, with_payload=False, gen_body="new generated body")
        expected = payload_paths(forest)

        merges = (
            ("canonical", protected_regions.merge_protected_regions),
            ("graph", graph_projections._merge_protected_regions),
        )
        for impl, fn in merges:
            try:
                out = fn(existing=existing, rendered=rendered, path="harness.md")
            except (protected_regions.ProtectedRegionError,
                    graph_projections.GraphProjectionError):
                stats[impl]["refused"] += 1
                continue
            except Exception:
                stats[impl]["error"] += 1
                continue
            stats[impl]["accepted"] += 1
            lost = [p for p in expected if p not in out]
            # Loss is not the only way to corrupt human content: a merge can
            # also emit a payload twice, or graft in whole spurious region
            # subtrees. A fix that only stops dropping bytes would still score
            # clean here without these two counters.
            duplicated = [p for p in expected if out.count(p) > 1]
            if duplicated:
                stats[impl]["dup_cases"] += 1
                stats[impl]["duplicated_payloads"] += len(duplicated)
            if len(_TOKEN.findall(out)) > len(_TOKEN.findall(existing)):
                stats[impl]["marker_growth_cases"] += 1
            if lost:
                stats[impl]["loss_cases"] += 1
                stats[impl]["lost_payloads"] += len(lost)
                if impl == "graph":
                    shape = describe_shape(forest)
                    shapes_with_graph_loss[shape] = shapes_with_graph_loss.get(shape, 0) + 1
            malformed = False
            xscope = False
            for payload, want in expected.items():
                if payload in lost:
                    continue
                # observed_path locates the FIRST occurrence. Where a payload
                # is duplicated and the first copy sits at the expected path,
                # a stray second copy elsewhere is not counted as substitution
                # -- the bias is conservative (it understates misbehaviour) and
                # dup_cases catches those separately. Payload tokens are
                # fixed-width so no token is a prefix of another; widening the
                # token space would need this revisited.
                got = observed_path(out, payload)
                if isinstance(got, _Malformed):
                    malformed = True
                    break
                if got != want:
                    xscope = True
            if malformed:
                stats[impl]["malformed_output"] += 1
            elif xscope:
                stats[impl]["xscope_cases"] += 1

    report = {
        "seed": args.seed,
        "trials": args.trials,
        "implementations": stats,
        "graph_loss_shapes_top": dict(
            sorted(shapes_with_graph_loss.items(), key=lambda kv: -kv[1])[:10]
        ),
    }
    for _impl, s in stats.items():
        acc = s["accepted"]
        s["loss_rate_of_accepted"] = round(s["loss_cases"] / acc, 5) if acc else None
    print(json.dumps(report, indent=2))
    return 0


def describe_shape(forest: list[Region]) -> str:
    def walk(rs: list[Region]) -> str:
        return "(" + ",".join(r.name + walk(r.children) for r in rs) + ")"
    return walk(forest)


if __name__ == "__main__":
    sys.exit(main())
