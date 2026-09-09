"""ULT-01b-1 — live execution observation.

Populates the AT3-103 ``ExecutionIdentity`` from trustworthy live observation
of the repository (git), the host environment and a declared toolchain, and
produces a content-bound ``ObservationReceipt``. Isolated from
``project_atlas.atlas3`` (which stays subprocess- and clock-free): this
package is the only place observation launches a process.

Honesty: OBSERVED != CLAIMED · UNKNOWN != FAILURE · OBSERVATION != AUTHORITY ·
STALE_OBSERVATION != CURRENT_OBSERVATION · SECRET != EVIDENCE_PAYLOAD.
"""

from project_atlas.execution_observation.git import (
    DEFAULT_BASE_REF,
    DEFAULT_REMOTE_NAME,
    GitObservation,
    observe_git,
)
from project_atlas.execution_observation.host import (
    ARCH_NORMALIZATION,
    DECLARED_TOOLCHAIN,
    EnvironmentObservation,
    ToolchainObservation,
    observe_environment,
    observe_toolchain,
)
from project_atlas.execution_observation.observe import (
    OBSERVE_CAPABILITY,
    OBSERVER_NAME,
    SLICE_ID,
    ObservationOutcome,
    observe_execution,
)
from project_atlas.execution_observation.runner import (
    CommandResult,
    CommandRunner,
    ObservationError,
    SubprocessRunner,
    build_child_env,
    resolve_executable,
)
from project_atlas.execution_observation.store import (
    OBSERVATION_RELATIVE,
    load_stored_receipt,
    receipt_locator,
    store_observation_receipt,
)

__all__ = [
    "ARCH_NORMALIZATION",
    "DECLARED_TOOLCHAIN",
    "DEFAULT_BASE_REF",
    "DEFAULT_REMOTE_NAME",
    "OBSERVATION_RELATIVE",
    "OBSERVER_NAME",
    "OBSERVE_CAPABILITY",
    "SLICE_ID",
    "CommandResult",
    "CommandRunner",
    "EnvironmentObservation",
    "GitObservation",
    "ObservationError",
    "ObservationOutcome",
    "SubprocessRunner",
    "ToolchainObservation",
    "build_child_env",
    "load_stored_receipt",
    "observe_environment",
    "observe_execution",
    "observe_git",
    "observe_toolchain",
    "receipt_locator",
    "resolve_executable",
    "store_observation_receipt",
]
