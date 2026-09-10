"""Which runtimes are supported, on this machine, with which capabilities.

`SUPPORTED != INSTALLED != AUTHENTICATED`. Three different facts, reported
separately, because a program that validates against a runtime nobody is
logged into fails at dispatch and not before.

A runtime appears here only when a real adapter exists for it, written against
that runtime's own verified interface. There is deliberately no generic
subprocess adapter: one would let any program claim support for a runtime
nobody has checked, and "we can launch a process" is not the same statement as
"we understand this runtime's output, permissions, and resume contract".

Capabilities are read from the adapters themselves, so this report cannot
drift from what the adapters actually declare.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any, Final

from project_atlas.orchestration.program.adapters.base import (
    AdapterCapabilities,
    AdapterUnavailableError,
    RuntimeAdapter,
)
from project_atlas.orchestration.program.adapters.claude_code import ClaudeCodeAdapter
from project_atlas.orchestration.program.adapters.codex import CodexAdapter
from project_atlas.orchestration.program.adapters.local_command import (
    FIXTURE_LABEL,
    LocalCommandAdapter,
)
from project_atlas.orchestration.program.profiles import AdapterKind


@dataclass(frozen=True)
class RuntimeSupport:
    """One runtime's honest support picture on this machine."""

    adapter: AdapterKind
    executable: str | None
    installed: bool
    version: str | None
    capabilities: AdapterCapabilities | None
    #: Capabilities this runtime does NOT have, named rather than omitted.
    unsupported: tuple[str, ...]
    #: What the runtime enforces itself, as opposed to what Atlas declares.
    runtime_enforced: tuple[str, ...]
    notes: tuple[str, ...]
    #: FIXTURE adapters are labelled so a report can never read as real support.
    is_fixture: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter.value,
            "executable": self.executable,
            "installed": self.installed,
            "version": self.version,
            "is_fixture": self.is_fixture,
            "capabilities": (
                {
                    "supports_resume": self.capabilities.supports_resume,
                    "supports_session_probe": self.capabilities.supports_session_probe,
                    "accepts_assigned_session": (
                        self.capabilities.accepts_assigned_session
                    ),
                    "supports_cost_limit": self.capabilities.supports_cost_limit,
                    "reports_cost": self.capabilities.reports_cost,
                    "supports_result_schema": self.capabilities.supports_result_schema,
                }
                if self.capabilities is not None
                else None
            ),
            "unsupported": list(self.unsupported),
            "runtime_enforced": list(self.runtime_enforced),
            "notes": list(self.notes),
        }


#: Capabilities NEITHER supported runtime has. Stated once, here, because the
#: temptation to assume one of them is what produces a supervisor that adopts
#: somebody's live terminal session.
UNIVERSALLY_UNSUPPORTED: Final[tuple[str, ...]] = (
    "attach to a running interactive session",
    "adopt a process this supervisor did not start",
    "guarantee a worker stays inside its declared mutation paths",
)


def _executable_for(adapter: AdapterKind) -> str | None:
    if adapter is AdapterKind.CLAUDE_CODE:
        return "claude"
    if adapter is AdapterKind.CODEX:
        return "codex"
    return None


def _adapter_for(adapter: AdapterKind) -> RuntimeAdapter:
    if adapter is AdapterKind.CLAUDE_CODE:
        return ClaudeCodeAdapter()
    if adapter is AdapterKind.CODEX:
        return CodexAdapter()
    return LocalCommandAdapter(("/bin/true",))


def describe(adapter: AdapterKind) -> RuntimeSupport:
    """Report one runtime, without launching a model call."""
    executable = _executable_for(adapter)
    installed = executable is None or shutil.which(executable) is not None
    impl = _adapter_for(adapter)
    capabilities = impl.capabilities if installed else None

    if adapter is AdapterKind.CLAUDE_CODE:
        return RuntimeSupport(
            adapter=adapter,
            executable=executable,
            installed=installed,
            version=capabilities.version if capabilities else None,
            capabilities=capabilities,
            unsupported=(
                *UNIVERSALLY_UNSUPPORTED,
                "filesystem confinement without --restricted",
                "a cost figure that is an actual charge rather than an estimate",
            ),
            runtime_enforced=(
                "--permission-mode",
                "--allowedTools / --disallowedTools / --tools",
                "--permission-prompts none",
                "--restricted (file tools confined to the working directories)",
                "--max-budget-usd (against the runtime's own estimate)",
            ),
            notes=(
                "session identity can be assigned before launch (--session-id), "
                "so an interrupted attempt stays addressable",
                "resume by session id works from any directory from 2.1.223",
                "--permission-prompts requires 2.1.259; below that an "
                "unattended run would wait for an approval nobody can give",
                "prefers ANTHROPIC_API_KEY over a logged-in subscription when "
                "both are present",
            ),
        )

    if adapter is AdapterKind.CODEX:
        return RuntimeSupport(
            adapter=adapter,
            executable=executable,
            installed=installed,
            version=capabilities.version if capabilities else None,
            capabilities=capabilities,
            unsupported=(
                *UNIVERSALLY_UNSUPPORTED,
                "assigning a session id before launch",
                "reporting cost in any currency",
                "a per-launch spend cap",
                "a single structured result object (events are JSONL)",
            ),
            runtime_enforced=(
                "--sandbox read-only | workspace-write | danger-full-access "
                "(a real filesystem boundary, verified by observation)",
                "--add-dir (additional writable roots)",
                "--cd (working root)",
            ),
            notes=(
                "mints its own thread id and announces it in the first "
                "thread.started event; the adapter streams that event file to "
                "disk so the identity survives a supervisor crash",
                "resume is `codex exec resume <thread-id>`",
                "reports token usage only, so this package reports cost as "
                "unknown rather than estimating one",
                "exits 0 on a task it could not perform: observed refusing a "
                "write under --sandbox read-only with a completed turn",
            ),
        )

    return RuntimeSupport(
        adapter=adapter,
        executable=None,
        installed=True,
        version=FIXTURE_LABEL,
        capabilities=capabilities,
        unsupported=(*UNIVERSALLY_UNSUPPORTED, "anything a model does"),
        runtime_enforced=("nothing; it runs a fixed argv",),
        notes=(
            "FIXTURE. Proves supervisor behaviour deterministically and "
            "without a model call. FIXTURE_RUN != REAL_RUNTIME_COMPATIBILITY",
        ),
        is_fixture=True,
    )


def describe_all() -> tuple[RuntimeSupport, ...]:
    return tuple(describe(kind) for kind in AdapterKind)


def preflight_report(adapter: AdapterKind) -> dict[str, Any]:
    """Describe a runtime and say why it could not run, if it could not.

    Authentication is not probed: doing so costs a model call on at least one
    of these runtimes, and a report that quietly spends money is not a report.
    Whether credentials work is established by the first dispatch, and the
    failure class it produces (`QUOTA_OR_CREDENTIAL`) says so plainly.
    """
    support = describe(adapter)
    payload = support.to_public_dict()
    payload["authentication_checked"] = False
    payload["authentication_note"] = (
        "not probed: a probe costs a model call on a real runtime. A "
        "credential or quota problem surfaces at first dispatch as the "
        "QUOTA_OR_CREDENTIAL failure class, which is never retried in a loop"
    )
    if not support.installed:
        payload["blocked"] = f"{support.executable!r} is not on PATH"
    return payload


def unavailable_reason(exc: AdapterUnavailableError) -> dict[str, str]:
    return {"code": getattr(exc, "code", "ADAPTER_UNAVAILABLE"), "detail": str(exc)}
