# FULL PRODUCT DEMO (D-177)

> **TECHNICAL DEMO** · **NOT RELEASE CERTIFIED** · **NOT AUTHENTIC PILOT** · **DEMO_FIXTURE**

Usable by someone who did not build Atlas.

## 1. Setup

```powershell
cd <project-atlas-clone>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
git rev-parse HEAD   # expect post-#504 main (or later)
```

## 2. Expected environment

- Windows or Linux
- Python 3.12+
- Network only for `pip install` (demo acts are local)
- Do **not** set `AUTHENTIC_ESTATE_ROOT` from `fixtures/demo`

## 3. Reset

```powershell
atlas demo full --reset --json
# Receipt: generated/ops/full-product-demo-receipt.json
# Estate fingerprint: docs/demo/DEMO-ESTATE-MANIFEST.json
```

Manual reset:

```powershell
Remove-Item -Recurse -Force .tmp\d177-full-product-demo -ErrorAction SilentlyContinue
```

## 4–14. Acts (orchestrated by `atlas demo full`)

| Act | What you should see |
| --- | --- |
| Discover | Manifest lists project-a/b/c; discovery ≠ ingest |
| Ingest / indexes / validate | Registry + indexes; conflicts OK as findings |
| Ask | Conflict-aware Ask2 JSON (`status=conflict`, evidence, unresolved>0). `status=unknown` + `ANSWER=null` on this fixture is ASK=FAIL, even if exit 0. |
| Unknown | project-c unknown fields → UNKNOWN honesty |
| Changed / source-health / next | Actionable lenses |
| Context | Agent-usable context without human re-explanation |
| Drift / Time Machine / DAG / API-Web-MCP | Extend harness; currently BLOCKED until lane complete |

## 15. Troubleshooting

| Symptom | Check |
| --- | --- |
| `init` fails non-empty | Delete work-root vault |
| ingest path mismatch | `--source` must match discover root |
| Ask empty | Ensure build-indexes PASS |
| FULL_LIVE_DEMO_READY false | Expected until all demo-critical acts PASS + P0/P1=0 |

## Honesty

Passing this demo yields at most **TECHNICAL DEMO — VERIFIED**.
It never stamps release certification or authentic pilot pass.
