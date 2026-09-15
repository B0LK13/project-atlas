"""TRUTH-UX-001 — LIVE web hooks must not label transport failure as demo_stub.

Firewall: existing production hooks only. Does not invent answers.
Does not change Time Machine (#356) or Ask (#357) branches.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS = REPO_ROOT / "apps" / "web" / "src" / "hooks"

HTTP_HOOKS = (
    "useLiveBrief.ts",
    "useLiveKnowledge.ts",
    "useLiveGraph.ts",
    "useOpsReceipts.ts",
)


def test_http_hooks_set_null_source_on_live_failure() -> None:
    for name in HTTP_HOOKS:
        text = (HOOKS / name).read_text(encoding="utf-8")
        assert "if (!liveApiDemoOnly())" in text
        assert 'setDataSource("live_api")' in text
        assert 'setDataSource("demo_stub")' in text
        after_ok = text.split("if (resp.ok)", 1)[1]
        http_fail = after_ok.split("} catch", 1)[0]
        assert "HTTP ${resp.status}" in http_fail, name
        assert "setDataSource(null)" in http_fail, name
        assert 'setDataSource("demo_stub")' not in http_fail, name
        catch = after_ok.split("} catch", 1)[1].split("return;")[0]
        assert "setDataSource(null)" in catch, name
        assert 'setDataSource("demo_stub")' not in catch, name


def test_estate_discovery_live_failure_is_not_demo() -> None:
    text = (HOOKS / "useEstateDiscovery.ts").read_text(encoding="utf-8")
    assert "LIVE discovery unavailable — not a demo stub" in text
    assert "demo_isolated: false" in text
    fail = text.split("} catch (err)")[1].split("} finally")[0]
    assert "setDataSource(null)" in fail
    assert 'setDataSource("demo_stub")' not in fail
