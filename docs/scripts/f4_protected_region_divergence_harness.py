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


def observed_path(text: str, payload: str) -> tuple[str, ...] | None:
    """RegionPath of ``payload`` in ``text``, by walking BEGIN/END markers."""
    import re

    idx = text.find(payload)
    if idx < 0:
        return None
    token = re.compile(r"<!--\s*(BEGIN|END) HUMAN:\s*([^\s>]+)\s*-->")
    stack: list[str] = []
    for m in token.finditer(text):
        if m.start() > idx:
            break
        if m.group(1) == "BEGIN":
            stack.append(m.group(2))
        elif stack:
            stack.pop()
    return tuple(stack)


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
    import re as _re

    from project_atlas import graph_projections, protected_regions

    def _doc(body: str, gen: str) -> str:
        return f"{GEN_START}\n{gen}\n{GEN_END}\n\n{body}"

    print(f"{'case':52} | {'canonical':44} | graph")
    print("-" * 132)
    for name, (body, pays) in _CASE_BODIES.items():
        existing = _doc(body, "OLD generated body")
        rendered = _doc(_re.sub(r"(?m)^PAY[-A-Z0-9]*\n", "", body), "NEW generated body")
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
            verdict = f"ACCEPT, drops {lost}" if lost else "ACCEPT, all payloads preserved"
            print(f"{name:52} | {verdict}")
    print()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20260907)
    args = ap.parse_args()

    from project_atlas import graph_projections, protected_regions

    run_named_cases()
    run_production_cases()

    stats = {
        impl: {"accepted": 0, "refused": 0, "loss_cases": 0, "lost_payloads": 0,
               "xscope_cases": 0, "error": 0}
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
            if lost:
                stats[impl]["loss_cases"] += 1
                stats[impl]["lost_payloads"] += len(lost)
                if impl == "graph":
                    shape = describe_shape(forest)
                    shapes_with_graph_loss[shape] = shapes_with_graph_loss.get(shape, 0) + 1
            xscope = any(
                p not in lost and observed_path(out, p) != expected[p] for p in expected
            )
            if xscope:
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
