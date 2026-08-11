#!/usr/bin/env python3
"""Verify repo-native dependency integrity manifests (SEC-027 / SEC-028).

LOCAL_SOURCE (editable project-atlas) is distinguished from THIRD_PARTY lock hashes.
Fail-closed on SHA-256 mismatch. Does not claim external security certification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deps/integrity.json (SEC-027)")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Integrity manifest path (default: <repo>/deps/integrity.json)",
    )
    args = parser.parse_args()
    root: Path = args.repo_root.resolve()
    manifest_path = (args.manifest or (root / "deps" / "integrity.json")).resolve()
    if not manifest_path.is_file():
        print(f"FAIL: missing integrity manifest: {manifest_path}", file=sys.stderr)
        return 1
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = data.get("artifacts") or {}
    if not artifacts:
        print("FAIL: integrity manifest has no artifacts", file=sys.stderr)
        return 1
    failed = 0
    for rel, meta in sorted(artifacts.items()):
        path = root / rel
        expected = (meta or {}).get("sha256")
        if not expected:
            print(f"FAIL: {rel}: missing sha256 in manifest", file=sys.stderr)
            failed += 1
            continue
        if not path.is_file():
            print(f"FAIL: {rel}: file missing at {path}", file=sys.stderr)
            failed += 1
            continue
        actual = _sha256(path)
        if actual != expected:
            print(
                f"FAIL: {rel}: sha256 mismatch expected={expected} actual={actual}",
                file=sys.stderr,
            )
            failed += 1
        else:
            print(f"OK  {rel} sha256={actual}")
    if failed:
        print(f"DEP_INTEGRITY=FAIL count={failed}", file=sys.stderr)
        print("EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES", file=sys.stderr)
        print("CODEX_VALIDATED=NO", file=sys.stderr)
        return 1
    print("DEP_INTEGRITY=PASS")
    print("EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES")
    print("CODEX_VALIDATED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
