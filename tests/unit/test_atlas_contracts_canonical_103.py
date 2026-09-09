"""AT3-103 — canonical JSON + content digest (identity, not authority)."""

from __future__ import annotations

import hashlib
import json

import pytest

from atlas_contracts.canonical import (
    CanonicalizationError,
    canonical_json,
    content_digest,
    sha256_hex,
    short_id,
)

_UNICODE = {"name": "Zoë — 東京 🚀"}


def test_key_order_and_separators_are_canonical() -> None:
    a = {"b": 1, "a": {"z": [1, 2, {"y": None, "x": True}], "m": 2.5}}
    b = {"a": {"m": 2.5, "z": [1, 2, {"x": True, "y": None}]}, "b": 1}
    assert canonical_json(a) == canonical_json(b)
    assert canonical_json(a) == '{"a":{"m":2.5,"z":[1,2,{"x":true,"y":null}]},"b":1}'
    assert content_digest(a) == content_digest(b)


def test_non_ascii_is_escaped_so_bytes_are_platform_stable() -> None:
    text = canonical_json(_UNICODE)
    assert text.isascii()
    assert "\\u00eb" in text and "\\u6771" in text and "\\ud83d\\ude80" in text
    assert content_digest(_UNICODE) == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_ascii_digest_differs_from_the_ensure_ascii_false_fork() -> None:
    # Negative control D pins this: the repo carries an ensure_ascii=False fork
    # elsewhere; this helper must not silently drift onto it.
    fork = json.dumps(_UNICODE, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert content_digest(_UNICODE) != hashlib.sha256(fork.encode("utf-8")).hexdigest()


def test_tuple_and_list_canonicalize_identically() -> None:
    assert canonical_json({"k": (1, 2)}) == canonical_json({"k": [1, 2]})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_are_refused(value: float) -> None:
    with pytest.raises(CanonicalizationError):
        canonical_json({"v": value})


def test_non_string_keys_are_refused_instead_of_coerced() -> None:
    with pytest.raises(CanonicalizationError, match="non-string key"):
        canonical_json({1: "a"})
    with pytest.raises(CanonicalizationError, match="non-string key"):
        canonical_json({"outer": {True: "a"}})


def test_non_json_native_values_are_refused() -> None:
    with pytest.raises(CanonicalizationError, match="not JSON-native"):
        canonical_json({"s": {1, 2}})
    with pytest.raises(CanonicalizationError, match="not JSON-native"):
        canonical_json({"o": object()})


def test_sha256_hex_str_and_bytes_agree() -> None:
    assert sha256_hex("abc") == sha256_hex(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_short_id_requires_a_real_digest() -> None:
    digest = content_digest({"x": 1})
    assert short_id("run", digest) == f"run-{digest[:16]}"
    with pytest.raises(CanonicalizationError):
        short_id("run", "ABC")
    with pytest.raises(CanonicalizationError):
        short_id("run", digest, length=4)
