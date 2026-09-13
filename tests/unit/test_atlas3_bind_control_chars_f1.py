"""AT3-051/052-F1 — NUL/control characters cannot disguise implementer as verifier."""

from __future__ import annotations

import pytest

from project_atlas.atlas3.adv_bind import bind_adversarial_result
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.iv_bind import bind_independent_verification

_HEAD = "d692cb886c67244316b354b7ae1eaf264d0304b0"
_TREE = "c6d8435e3eb39f71e14ecfe1afe4e82ace451810"


def test_iv_nul_suffix_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_independent_verification(
            candidate_head=_HEAD,
            candidate_tree=_TREE,
            observed_head=_HEAD,
            observed_tree=_TREE,
            iv_result="PASS",
            verifier_id="implementer\x00",
            package_id="AT3-021",
        )
    assert exc.value.code == "VERIFIER_ID_INVALID"


def test_adv_nul_suffix_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_adversarial_result(
            candidate_head=_HEAD,
            candidate_tree=_TREE,
            observed_head=_HEAD,
            observed_tree=_TREE,
            adv_result="PASS",
            adv_id="model\x00",
            package_id="AT3-052",
        )
    assert exc.value.code == "ADV_ID_INVALID"


def test_iv_zwsp_suffix_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_independent_verification(
            candidate_head=_HEAD,
            candidate_tree=_TREE,
            observed_head=_HEAD,
            observed_tree=_TREE,
            iv_result="PASS",
            verifier_id="implementer\u200b",
            package_id="AT3-021",
        )
    assert exc.value.code == "VERIFIER_ID_INVALID"


def test_iv_homoglyph_implementer_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_independent_verification(
            candidate_head=_HEAD,
            candidate_tree=_TREE,
            observed_head=_HEAD,
            observed_tree=_TREE,
            iv_result="PASS",
            verifier_id="\u0456mplementer",
            package_id="AT3-021",
        )
    assert exc.value.code == "VERIFIER_ID_INVALID"


def test_plain_forbidden_ids_still_fail() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_independent_verification(
            candidate_head=_HEAD,
            candidate_tree=_TREE,
            observed_head=_HEAD,
            observed_tree=_TREE,
            iv_result="PASS",
            verifier_id="implementer",
            package_id="AT3-021",
        )
    assert exc.value.code == "IMPLEMENTER_IS_VERIFIER"


def test_honest_verifier_still_binds() -> None:
    bound = bind_independent_verification(
        candidate_head=_HEAD,
        candidate_tree=_TREE,
        observed_head=_HEAD,
        observed_tree=_TREE,
        iv_result="PASS",
        verifier_id="bc-independent-iv",
        package_id="AT3-021",
    )
    assert bound["bound"] is True
    assert bound["merge_authorization"] == "NOT_GRANTED"
    assert bound["implementer_is_verifier"] is False
