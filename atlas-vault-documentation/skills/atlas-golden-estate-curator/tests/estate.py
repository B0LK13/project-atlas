"""Synthetic fixture estate for curator tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def _init_repo(path: Path, *, readme: str | None, commit: bool = True) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init")
    _git(path, "config", "user.email", "estate@example.test")
    _git(path, "config", "user.name", "Estate Fixture")
    if readme is not None:
        (path / "README.md").write_text(readme, encoding="utf-8")
    (path / "src").mkdir(exist_ok=True)
    (path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    if commit:
        _git(path, "add", ".")
        _git(path, "commit", "-m", "fixture")


def fingerprint(root: Path) -> str:
    rows: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name != ".git"]
        dirnames.sort()
        filenames.sort()
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        rows.append(f"D:{rel_dir}")
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                rows.append(f"L:{Path(rel_dir, name).as_posix()}->{os.readlink(path)}")
                continue
            data = path.read_bytes()
            rows.append(f"F:{Path(rel_dir, name).as_posix()}:{len(data)}:{data!r}")
    return "\n".join(rows)


def build_fixture_estate(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)

    healthy = root / "healthy-git"
    _init_repo(healthy, readme="# Healthy\n")

    nongit = root / "non-git-folder"
    nongit.mkdir()
    (nongit / "README.md").write_text("# Loose folder\n", encoding="utf-8")

    nested = root / "nested-parent"
    _init_repo(nested, readme="# Parent\n")
    child = nested / "vendor" / "nested-child"
    _init_repo(child, readme="# Nested child\n")

    mono = root / "monorepo"
    _init_repo(mono, readme="# Mono\n")
    (mono / "packages" / "a").mkdir(parents=True)
    (mono / "packages" / "a" / "pyproject.toml").write_text("[project]\nname='a'\n", encoding="utf-8")

    dirty = root / "dirty-worktree"
    _init_repo(dirty, readme="# Dirty\n")
    (dirty / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")

    no_readme = root / "missing-readme"
    _init_repo(no_readme, readme=None)

    stale = root / "stale-docs"
    _init_repo(stale, readme="# Old\n")
    os.utime(stale / "README.md", (1_000_000, 1_000_000))
    os.utime(stale / "src" / "app.py", (2_000_000_000, 2_000_000_000))

    test_fail = root / "test-failure"
    _init_repo(test_fail, readme="# Tests failed\n")
    signal = test_fail / ".atlas-estate" / "signals"
    signal.mkdir(parents=True)
    (signal / "test_failed").write_text("1\n", encoding="utf-8")
    _git(test_fail, "add", ".")
    _git(test_fail, "commit", "-m", "signal")

    build_fail = root / "build-failure"
    _init_repo(build_fail, readme="# Build failed\n")
    bsignal = build_fail / ".atlas-estate" / "signals"
    bsignal.mkdir(parents=True)
    (bsignal / "build_failed").write_text("1\n", encoding="utf-8")
    _git(build_fail, "add", ".")
    _git(build_fail, "commit", "-m", "signal")

    secret = root / "fake-secret"
    _init_repo(secret, readme="# Secret\n")
    (secret / ".env").write_text("aws_secret_access_key=NOT_A_REAL_SECRET_VALUE\n", encoding="utf-8")

    escape_target = root.parent / "outside-escape"
    escape_target.mkdir()
    (escape_target / "private.txt").write_text("outside\n", encoding="utf-8")
    junction = root / "junction-escape"
    junction.mkdir()
    (junction / "README.md").write_text("# Escape\n", encoding="utf-8")
    (junction / "escape-link").symlink_to(escape_target, target_is_directory=True)

    generated = root / "generated-dir"
    _init_repo(generated, readme="# Generated present\n")
    (generated / "node_modules" / "pkg").mkdir(parents=True)
    (generated / "node_modules" / "pkg" / "index.js").write_text("1\n", encoding="utf-8")

    first = root / "dup-a"
    _init_repo(first, readme="# Dup A\n")
    (first / ".atlas-project.yaml").write_text("id: shared-id\n", encoding="utf-8")
    second = root / "dup-b"
    _init_repo(second, readme="# Dup B\n")
    (second / ".atlas-project.yaml").write_text("id: shared-id\n", encoding="utf-8")

    malice = root / "malicious-build"
    _init_repo(malice, readme="# Malice\n")
    script = malice / "build.sh"
    script.write_text("#!/bin/sh\necho executed > EXECUTED\nrm -rf /tmp/should-not-happen\n", encoding="utf-8")
    script.chmod(0o755)

    return root
