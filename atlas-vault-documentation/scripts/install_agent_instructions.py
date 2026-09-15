#!/usr/bin/env python3
"""Generate deterministic agent-native Atlas instruction adapters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_control import skill_compiler, skill_loader  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent.parent / ".generated-agent-instructions")
    parser.add_argument("--project-id", default="<project-id>")
    parser.add_argument("--vault-id", default="<vault-id>")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    skill = skill_loader.load(Path(__file__).resolve().parent.parent / "skills" / "atlas-governed-work")
    paths = skill_compiler.generate(skill, args.output, project_id=args.project_id, vault_id=args.vault_id)
    result = {"ok": True, "skill_id": skill.skill_id, "skill_version": skill.version, "skill_sha256": skill.sha256, "files": [str(path) for path in paths]}
    print(json.dumps(result) if args.json_output else "generated " + str(len(paths)) + " adapters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
