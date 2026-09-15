# Wave 15 Local acceptance packet

Cloud must **not** self-certify authentic Local evidence.

```
LOCAL_WAVE15_PACKET_READY = YES
LOCAL_AUTHENTIC_EVIDENCE = NOT_SELF_CERTIFIED
```

## Local matrix (owner)

| Check | How to exercise | Pass looks like |
|---|---|---|
| API contract | `GET` each intelligence route with Bearer `api.read` | envelope has `status`, `honesty`, `as_of`, `reasons`, `authority`, `limitations`, `canonical_write=false` |
| Project isolation | two projects in one vault | harbor-api payload never contains the other project's values |
| Truth states | empty / filtered / contested / stale fixtures | `NO_DATA` ≠ `VALID_EMPTY` ≠ `NO_MATCH`; `CONTESTED` ≠ resolved; `STALE` ≠ invalid |
| Failure honesty | `as_of=now`, bad project id, POST, unsupported kind | `MALFORMED_INPUT` / `UNSUPPORTED_SCOPE` / `405 writes-forbidden`; never demo |
| Write/auth absence | POST intelligence + inspect OperatorProfile | no `api.write` / `vault.write` expansion |
| Performance | optional dense 10k library rerun | residual remains MAJOR unless new evidence |

## Suggested commands

```bash
atlas live api-serve --vault <local-vault>
# then GET /v1/intelligence/evidence?project=<id>
# GET /v1/intelligence/conflicts?project=<id>
# GET /v1/project-state?project=<id>
# GET /v1/project-attention?project=<id>
# GET /v1/portfolio-state
# GET /v1/intelligence/query?project=<id>&kind=decision
```

Do not treat Cloud pytest as Local authentic-pilot evidence.
