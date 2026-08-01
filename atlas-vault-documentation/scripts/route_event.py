#!/usr/bin/env python3
"""Route one verified normalized event into the Atlas vault (AS-WP-003).

Exit codes:

- 0: routed, idempotent replay, or routing disabled by configuration;
- 2: usage error (arguments, configuration, unsafe identifiers);
- 3: operational error (unsafe path, lock unavailable, I/O);
- 4: event acceptance failure (unverified, malformed provenance, hash
  mismatch, unsupported schema, duplicate conflicting event);
- 5: routing failure (plan, staging, region, or transaction failure).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import atlas_config
import capture_event
from internal import atlas_router, event_reader, project_identity

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_OPERATIONAL = 3
EXIT_ACCEPTANCE = 4
EXIT_ROUTING_FAILED = 5

FAIL_CATEGORY_EXITS = {
    "duplicate-conflict": EXIT_ACCEPTANCE,
    "lock-unavailable": EXIT_OPERATIONAL,
    "stale-transaction": EXIT_OPERATIONAL,
    "promotion-failed": EXIT_OPERATIONAL,
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--normalized-event", type=Path, required=True)
    result.add_argument("--vault", type=Path)
    result.add_argument("--config", type=Path)
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--json", action="store_true", dest="json_output")
    return result


def _bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def routing_settings(config: Mapping[str, Any]) -> atlas_router.RoutingSettings:
    section = config.get("routing", {})
    if not isinstance(section, Mapping):
        section = {}

    def get(key: str, default: Any) -> Any:
        value = section.get(key)
        return default if value is None else value

    return atlas_router.RoutingSettings(
        projects_root=str(get("projects_root", "projects")),
        state_root=str(get("state_root", "routing/state")),
        receipts_root=str(get("receipts_root", "routing/receipts")),
        failures_root=str(get("failures_root", "routing/failures")),
        require_verified_normalization=_bool(get("require_verified_normalization", True), True),
        event_placement=str(get("event_placement", "reference")),
        project_log_enabled=_bool(get("project_log", True), True),
        work_package_projection=_bool(get("work_package_projection", True), True),
        project_index_projection=_bool(get("project_index_projection", True), True),
        stale_lock_seconds=float(get("stale_lock_seconds", 300)),
        lock_wait_seconds=float(get("lock_wait_seconds", 30)),
    )


def _emit(payload: dict[str, Any], args: argparse.Namespace, human: str) -> None:
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(human)


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config, _ = atlas_config.load_config(args.config)
    except atlas_config.ConfigError as exc:
        print(f"ERROR: {capture_event.redact(str(exc))}", file=sys.stderr)
        return EXIT_USAGE

    vault_value = atlas_config.resolve(args.vault, "ATLAS_VAULT", config, "atlas", "vault")
    if not vault_value:
        print("ERROR: provide --vault, ATLAS_VAULT, or atlas.vault", file=sys.stderr)
        return EXIT_USAGE
    vault_root = Path(vault_value).expanduser().resolve()

    if not _bool(atlas_config.config_value(config, "routing", "enabled"), True):
        _emit(
            {"ok": True, "status": "disabled", "message": "routing disabled by configuration"},
            args, "Routing disabled.",
        )
        return EXIT_OK

    settings = routing_settings(config)
    event, problems = event_reader.read_event(
        args.normalized_event, vault_root=vault_root
    )
    if event is None:
        payload = {
            "ok": False, "status": "rejected", "category": "acceptance-failed",
            "problems": problems,
        }
        _emit(payload, args, "Event rejected:")
        if not args.json_output:
            for problem in problems:
                print(f"ERROR: {problem}", file=sys.stderr)
        return EXIT_ACCEPTANCE

    try:
        identity = project_identity.resolve_identity(
            event_project_id=event.project_id,
            event_project_slug=event.project_slug,
            repository=event.repository,
            config=config,
        )
    except project_identity.IdentityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        _emit(
            {"ok": False, "status": "rejected", "category": exc.category,
             "event_id": event.event_id, "message": str(exc)},
            args, f"Identity resolution failed: {exc}",
        )
        return EXIT_ACCEPTANCE

    if args.dry_run:
        from internal import route_planner

        receipt_id = atlas_router.receipt_id_for(event, identity.project_id)
        plan = route_planner.build_plan(
            event, identity,
            projects_root=settings.projects_root,
            state_root=settings.state_root,
            receipts_root=settings.receipts_root,
            receipt_id=receipt_id,
            work_package_projection=settings.work_package_projection,
            project_index_projection=settings.project_index_projection,
        )
        plan_problems = route_planner.validate_plan(plan)
        payload = {
            "ok": not plan_problems,
            "status": "dry-run",
            "plan_sha256": route_planner.plan_hash(plan),
            "problems": plan_problems,
            "plan": plan,
        }
        _emit(payload, args, f"Dry run: plan {route_planner.plan_hash(plan)[:12]}")
        return EXIT_OK if not plan_problems else EXIT_USAGE

    result = atlas_router.route(
        event, identity,
        vault_root=vault_root, settings=settings, redact=capture_event.redact,
    )
    payload = result.as_dict()
    payload.pop("plan", None)
    _emit(payload, args, f"{result.status}: {result.event_id} — {result.message}")
    if result.ok:
        return EXIT_OK
    if not args.json_output:
        print(f"ERROR: {result.message}", file=sys.stderr)
    return FAIL_CATEGORY_EXITS.get(result.category or "", EXIT_ROUTING_FAILED)


if __name__ == "__main__":
    raise SystemExit(main())
