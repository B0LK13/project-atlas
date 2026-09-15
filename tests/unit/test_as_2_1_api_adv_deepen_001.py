"""AS-2.1-API-ADV-DEEPEN — LIVE_API adversarial deepen (Track A / ADV sole-writer).

Covers invalid IDs, cross-project isolation, oversized payload, authz bypass
attempts, duplicate actions, and internal path leakage. Non-pilot; does not
unlock authentic PILOT / SYNC-AUTH / TWIN-AUTH / release certification.
"""

from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import MAX_POST_BYTES, serve_api, session_credentials
from project_atlas.authz import OperatorProfile, default_operator, elevated_operator
from project_atlas.web_actions import load_action_ledger


def _start(vault: Path, *, operator: OperatorProfile | None = None) -> tuple[Any, str, int]:
    server = serve_api(vault, host="127.0.0.1", port=0, operator=operator)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, str(host), int(port)


def _read_auth(server: Any) -> dict[str, str]:
    return session_credentials(server).auth_headers()


def _priv_auth(server: Any) -> dict[str, str]:
    creds = session_credentials(server)
    if creds.privileged_token is None:
        return creds.auth_headers()
    return creds.auth_headers(privileged=True)


def _post(
    host: str,
    port: int,
    payload: dict[str, Any] | bytes,
    *,
    headers: dict[str, str] | None = None,
    path: str = "/v1/actions",
    auth: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    if isinstance(payload, dict):
        raw = json.dumps(payload).encode("utf-8")
        hdrs = {"Content-Type": "application/json", **(auth or {}), **(headers or {})}
    else:
        raw = payload
        hdrs = {"Content-Type": "application/json", **(auth or {}), **(headers or {})}
        if "Content-Length" not in hdrs:
            hdrs["Content-Length"] = str(len(raw))
    req = Request(
        f"http://{host}:{port}{path}",
        data=raw,
        headers=hdrs,
        method="POST",
    )
    try:
        with urlopen(req, timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return int(resp.status), body
    except HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8"))
        return int(exc.code), body


def _get(
    host: str,
    port: int,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    auth: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    hdrs = {**(auth or {}), **(headers or {})}
    req = Request(f"http://{host}:{port}{path}", headers=hdrs)
    try:
        with urlopen(req, timeout=2) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        return int(exc.code), json.loads(exc.read().decode("utf-8"))


def _seed_two_projects(vault: Path) -> None:
    for name in ("alpha", "beta"):
        proj = vault / "projects" / name
        proj.mkdir(parents=True)
        (proj / "project.md").write_text(f"# {name}\n", encoding="utf-8")


# --- ADV-2.1-30: invalid action IDs -----------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        " ",
        "UPPER",
        "has space",
        "../escape",
        "a/b",
        "act_id",
        "1leading-digit",
        "x" * 80,
        "act\nid",
        "act..id",
    ],
)
def test_adv_api_rejects_invalid_action_ids(tmp_path: Path, bad_id: str) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    op = elevated_operator("adv-id", extra={"web.action"})
    server, host, port = _start(vault, operator=op)
    try:
        code, body = _post(
            host,
            port,
            {"action_id": bad_id, "action_type": "refresh-status", "payload": {}},
            auth=_priv_auth(server),
        )
        assert code == 400
        assert "web-action-id-invalid" in body["error"]
        assert load_action_ledger(vault)["transactions"] == []
    finally:
        server.shutdown()


def test_adv_api_rejects_forbidden_action_type(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    op = elevated_operator("adv-type", extra={"web.action"})
    server, host, port = _start(vault, operator=op)
    try:
        code, body = _post(
            host,
            port,
            {
                "action_id": "act-ok",
                "action_type": "promote-claim",
                "payload": {},
            },
            auth=_priv_auth(server),
        )
        assert code == 400
        assert "web-action-type-forbidden" in body["error"]
    finally:
        server.shutdown()


# --- ADV-2.1-31: cross-project isolation ------------------------------------


def test_adv_api_cross_project_lists_only_vault_relative_paths(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "v"
    _seed_two_projects(vault)
    # Sibling vault must not leak into the served vault's inventory.
    foreign = tmp_path / "foreign"
    (foreign / "projects" / "gamma").mkdir(parents=True)
    server, host, port = _start(vault)
    try:
        code, body = _get(host, port, "/v1/projects", auth=_read_auth(server))
        assert code == 200
        ids = {row["project_id"] for row in body["projects"]}
        assert ids == {"alpha", "beta"}
        assert "gamma" not in ids
        for row in body["projects"]:
            assert row["path"] == f"projects/{row['project_id']}"
            assert not Path(row["path"]).is_absolute()
    finally:
        server.shutdown()


def test_adv_api_cross_project_authority_payload_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _seed_two_projects(vault)
    op = elevated_operator("adv-xp", extra={"web.action"})
    server, host, port = _start(vault, operator=op)
    try:
        for forbidden in (
            {"claim_id": "claim-beta-1", "project_id": "beta"},
            {"authority": True, "project_id": "alpha"},
            {"promote": True, "target_project": "beta"},
            {"vault_write": "projects/beta/project.md"},
        ):
            code, body = _post(
                host,
                port,
                {
                    "action_id": f"xp-{hash(frozenset(forbidden)) & 0xFFFF:04x}",
                    "action_type": "acknowledge-finding",
                    "payload": forbidden,
                },
                auth=_priv_auth(server),
            )
            assert code == 400
            assert "web-action-authority-fields-forbidden" in body["error"]
        # No Layer-B mutation from rejected cross-project authority attempts.
        assert (vault / "projects" / "beta" / "project.md").read_text(
            encoding="utf-8"
        ) == "# beta\n"
        assert load_action_ledger(vault)["transactions"] == []
    finally:
        server.shutdown()


# --- ADV-2.1-32: oversized payload ------------------------------------------


def test_adv_api_oversized_payload_exact_boundary(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    op = elevated_operator("adv-size", extra={"web.action"})
    server, host, port = _start(vault, operator=op)
    try:
        # Declare oversize via Content-Length (avoid huge socket writes on Windows).
        conn = http.client.HTTPConnection(host, port, timeout=2)
        try:
            conn.putrequest("POST", "/v1/actions")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Authorization", _priv_auth(server)["Authorization"])
            conn.putheader("Content-Length", str(MAX_POST_BYTES + 1))
            conn.endheaders()
            conn.send(b"{}")
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            body = json.loads(raw)
            assert resp.status == 413
            assert body["error"] == "payload-too-large"
            assert body["max_post_bytes"] == MAX_POST_BYTES
        finally:
            conn.close()
        assert load_action_ledger(vault)["transactions"] == []
    finally:
        server.shutdown()


def test_adv_api_invalid_content_length_fail_closed(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    op = elevated_operator("adv-cl", extra={"web.action"})
    server, host, port = _start(vault, operator=op)
    try:
        code, body = _post(
            host,
            port,
            b'{"action_id":"act-cl","action_type":"refresh-status"}',
            headers={"Content-Length": "not-a-number"},
            auth=_priv_auth(server),
        )
        assert code == 400
        assert "content-length-invalid" in body["error"]
    finally:
        server.shutdown()


# --- ADV-2.1-33: authz bypass attempts --------------------------------------


def test_adv_api_default_operator_cannot_post_actions(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    assert not default_operator().allows("web.action")
    server, host, port = _start(vault)  # default operator
    try:
        code, body = _post(
            host,
            port,
            {
                "action_id": "bypass-1",
                "action_type": "refresh-status",
                "payload": {},
            },
            auth=_read_auth(server),
        )
        assert code == 400
        assert "authz-denied:web.action" in body["error"]
        assert load_action_ledger(vault)["transactions"] == []
    finally:
        server.shutdown()


def test_adv_api_header_spoof_does_not_elevate(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    server, host, port = _start(vault)
    try:
        spoof_headers = {
            "X-Operator-Id": "root",
            "X-Atlas-Capabilities": "vault.write,web.action,autonomy.l3",
            "Authorization": "Bearer fake-token",
            "X-Forwarded-For": "8.8.8.8",
        }
        code, body = _post(
            host,
            port,
            {
                "action_id": "spoof-1",
                "action_type": "refresh-status",
                "payload": {"vault_write": True},
            },
            headers=spoof_headers,
        )
        # SEC-009: forged Bearer is auth-invalid (not capability elevation).
        assert code == 401
        assert body["error"] == "auth-invalid"
        assert body.get("accepted") is not True
        code_put, body_put = _get(host, port, "/v1/authz", auth=_read_auth(server))
        assert code_put == 200
        assert body_put["authority"] is False
        assert body_put["write_enabled"] is False
        assert "vault.write" not in body_put["capabilities"]
        assert "web.action" not in body_put["capabilities"]
    finally:
        server.shutdown()


def test_adv_api_non_action_writes_forbidden(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    op = elevated_operator("adv-w", extra={"web.action", "vault.write"})
    server, host, port = _start(vault, operator=op)
    try:
        for path in ("/v1/projects", "/v1/knowledge", "/v1/meta", "/v1/snapshot"):
            code, body = _post(
                host,
                port,
                {"action_id": "w1", "action_type": "refresh-status"},
                path=path,
                auth=_priv_auth(server),
            )
            assert code == 405
            assert body["error"] == "writes-forbidden"
        for method in ("PUT", "DELETE"):
            req = Request(
                f"http://{host}:{port}/v1/actions",
                data=b"{}",
                method=method,
                headers={
                    "Content-Type": "application/json",
                    **_priv_auth(server),
                },
            )
            with pytest.raises(HTTPError) as excinfo:
                urlopen(req, timeout=2)
            assert excinfo.value.code == 405
            body = json.loads(excinfo.value.read().decode("utf-8"))
            assert body["error"] == "writes-forbidden"
    finally:
        server.shutdown()


# --- ADV-2.1-34: duplicate actions ------------------------------------------


def test_adv_api_duplicate_action_id_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    op = elevated_operator("adv-dup", extra={"web.action"})
    server, host, port = _start(vault, operator=op)
    try:
        first = {
            "action_id": "act-once",
            "action_type": "refresh-status",
            "payload": {},
        }
        code1, body1 = _post(host, port, first, auth=_priv_auth(server))
        assert code1 == 200
        assert body1["accepted"] is True
        code2, body2 = _post(host, port, first, auth=_priv_auth(server))
        assert code2 == 400
        assert "web-action-id-duplicate" in body2["error"]
        ledger = load_action_ledger(vault)
        assert len(ledger["transactions"]) == 1
        assert ledger["transactions"][0]["action_id"] == "act-once"
    finally:
        server.shutdown()


# --- ADV-2.1-35: internal path leakage --------------------------------------


def test_adv_api_traversal_404_does_not_leak_filesystem(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    # Plant a secret outside the vault API surface; traversal must not open it.
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("LEAK-MARKER-DO-NOT-EMIT", encoding="utf-8")
    server, host, port = _start(vault)
    abs_vault = str(vault.resolve())
    try:
        probes = [
            "/v1/../../etc/passwd",
            "/v1/projects/../../.env",
            "/v1/meta/%2e%2e/%2e%2e/windows/system32",
            "/v1/actions/../../../generated/ops",
            "/v1/file/outside-secret.txt",
            "/v1/../outside-secret.txt",
        ]
        for path in probes:
            code, body = _get(host, port, path, auth=_read_auth(server))
            assert code == 404
            assert body["error"] == "not-found"
            dumped = json.dumps(body, sort_keys=True)
            assert "LEAK-MARKER-DO-NOT-EMIT" not in dumped
            assert abs_vault not in dumped
            assert str(secret.resolve()) not in dumped
            assert "\\" not in dumped  # no Windows filesystem path echo
            assert "errno" not in dumped.lower()
            assert "traceback" not in dumped.lower()
            # Echoed path is the request path only (no resolved open).
            assert body.get("path", "").startswith("/")
    finally:
        server.shutdown()


def test_adv_api_error_bodies_omit_absolute_vault_path(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    op = elevated_operator("adv-leak", extra={"web.action"})
    server, host, port = _start(vault, operator=op)
    abs_vault = str(vault.resolve())
    try:
        code, body = _post(
            host,
            port,
            b"{not-json",
            auth=_priv_auth(server),
        )
        assert code == 400
        dumped = json.dumps(body)
        assert abs_vault not in dumped
        assert "generated/ops/web-actions" not in dumped

        code2, body2 = _get(host, port, "/v1/snapshot", auth=_read_auth(server))
        assert code2 == 200
        dumped2 = json.dumps(body2)
        assert abs_vault not in dumped2
        for row in body2.get("projects", []):
            assert row["path"].startswith("projects/")
    finally:
        server.shutdown()
