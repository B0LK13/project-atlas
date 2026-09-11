"""G4b -- start identity must be unique across a reboot.

(pid, ticks-since-boot) repeats after a reboot while the identity files that
record it survive one. The boot component closes that. The upgrade path is
the part worth reviewing: an identity in the old two-field form must read as
UNKNOWN, never GONE -- calling a running worker dead across an upgrade is the
one direction B1 exists to prevent.
"""

from __future__ import annotations


def test_g4b_start_identity_survives_a_reboot_and_old_records_are_not_gone() -> None:
    """G4b: (pid, starttime) herhaalt zich na een reboot; de boot-id niet.

    En een identity uit het oude formaat mag daardoor niet als GONE lezen: dat
    zou een draaiende worker over een upgrade heen doodverklaren.
    """
    import os

    from project_atlas.orchestration.program.recovery import Liveness, process_liveness
    from project_atlas.orchestration.sdk.host import process_start_identity

    current = process_start_identity(os.getpid())
    assert current.startswith("linux:"), "deze test is Linux-specifiek"
    assert len(current.split(":")) == 3, (
        f"start identity draagt geen boot-component: {current}"
    )

    verdict, _ = process_liveness(os.getpid(), current)
    assert verdict is Liveness.ALIVE

    legacy = ":".join(current.split(":")[:2])
    verdict, reason = process_liveness(os.getpid(), legacy)
    assert verdict is Liveness.UNKNOWN, (
        f"een pre-boot-id identity leest als {verdict}, niet UNKNOWN: {reason}"
    )

    verdict, _ = process_liveness(os.getpid(), "linux:999999:ffffffffffffffff")
    assert verdict is Liveness.GONE, "een echt andere identity moet GONE zijn"
