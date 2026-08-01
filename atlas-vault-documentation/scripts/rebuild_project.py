#!/usr/bin/env python3
"""Rebuild one project's projections from routing state (AS-WP-003).

Projections are pure functions of ``routing/state/<project>.json``;
rebuilding renders them deterministically and writes only files whose
content actually changed. Use after manual page repair or to prove
that projections are current (a no-op rebuild means consistency).

Exit codes: 0 ok (or nothing changed), 2 usage, 3 operational.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import atlas_config  # noqa: E402
import capture_event  # noqa: E402
from internal import (  # noqa: E402
    generated_regions,
    project_identity,
    project_log,
    project_pages,
    routing_state,
    transaction,
    work_package_projection,
)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_OPERATIONAL = 3


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--project-id", required=True)
    result.add_argument("--vault", type=Path)
    result.add_argument("--config", type=Path)
    result.add_argument("--from-routing-state", action="store_true",
                        help="Kept for CLI clarity; rebuilds always use routing state.")
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--json", action="store_true", dest="json_output")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config, _ = atlas_config.load_config(args.config)
    except atlas_config.ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USAGE
    vault_value = atlas_config.resolve(args.vault, "ATLAS_VAULT", config, "atlas", "vault")
    if not vault_value:
        print("ERROR: provide --vault, ATLAS_VAULT, or atlas.vault", file=sys.stderr)
        return EXIT_USAGE
    vault_root = Path(vault_value).expanduser().resolve()

    project_id = args.project_id
    if not project_identity.SAFE_PROJECT_ID.fullmatch(project_id):
        print(f"ERROR: unsafe project id: {project_id!r}", file=sys.stderr)
        return EXIT_USAGE

    state_dir = vault_root / "routing" / "state"
    try:
        state = routing_state.load_state(state_dir, project_id)
    except (ValueError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_OPERATIONAL

    identity = project_identity.resolve_identity(
        event_project_id=None,
        event_project_slug=project_id,
        repository=None,
        config=config,
    )
    project_rel = f"projects/{project_id}"

    staged: dict[str, str] = {}
    log_rel = f"{project_rel}/project-log.md"
    index_rel = f"{project_rel}/index.md"

    def read(rel: str) -> str | None:
        path = vault_root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else None

    try:
        staged[log_rel] = project_log.render_log_page(
            state, display_name=identity.display_name,
            from_file_rel=log_rel, project_rel=project_rel,
            existing=read(log_rel),
        )
        for wp, summary in sorted(state.work_packages.items()):
            wp_rel = f"{project_rel}/work-packages/{wp}.md"
            wp_events = [
                r for r in state.routed_events.values()
                if r.work_package_id == wp
            ]
            staged[wp_rel] = work_package_projection.render_work_package_page(
                wp, summary, wp_events,
                state=state, project_rel=project_rel, from_file_rel=wp_rel,
                existing=read(wp_rel),
            )
        staged[index_rel] = project_pages.render_index_page(
            state, identity, project_rel=project_rel, from_file_rel=index_rel,
            existing=read(index_rel),
        )
    except generated_regions.RegionError as exc:
        print(f"ERROR: generated region conflict: {exc}", file=sys.stderr)
        return EXIT_OPERATIONAL

    changed = sorted(rel for rel in staged if read(rel) != staged[rel])
    payload = {
        "ok": True,
        "project_id": project_id,
        "files_staged": len(staged),
        "files_changed": changed,
        "dry_run": bool(args.dry_run),
    }
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False) if args.json_output
              else f"Dry run: {len(changed)} file(s) would change")
        return EXIT_OK

    txn = transaction.Transaction()
    for rel in changed:
        txn.stage(vault_root / rel, staged[rel], current=read(rel))
    lock = transaction.ProjectLock(state_dir / f"{project_id}.lock")
    try:
        with lock:
            txn.promote()
    except (transaction.PreconditionError, transaction.LockError, OSError) as exc:
        print(f"ERROR: {capture_event.redact(str(exc))}", file=sys.stderr)
        return EXIT_OPERATIONAL

    print(json.dumps(payload, ensure_ascii=False) if args.json_output
          else f"Rebuilt {project_id}: {len(changed)} file(s) changed")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
