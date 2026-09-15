# Wave 16 Local acceptance packet

Cloud must **not** self-certify authentic Local evidence.

```
LOCAL_WAVE16_PACKET_READY = YES
LOCAL_AUTHENTIC_EVIDENCE = NOT_SELF_CERTIFIED
```

## Local matrix (owner)

| Check | How to exercise | Pass looks like |
|---|---|---|
| Authentic project binding | open `/intelligence?project=<real-id>` | payload project matches query; no harbor-api default |
| Navigation | switch Knowledge → Intelligence → Ask → Time Machine → Roadmap | `?project=` preserved; Ask still vault-wide; Time Machine `from`/`to` not copied onto Intelligence |
| API/Web parity | compare LIVE_API JSON to rendered cards | same honesty class; inspectable provenance |
| Truth rendering | contested / stale / empty vault | CONTESTED / STALE / NO_DATA / UNKNOWN chips; never healthy |
| Failure rendering | stop LIVE_API | HTTP_FAILURE banner; not DEMO unless `VITE_ATLAS_DEMO_ONLY` |
| Cross-project leakage | two projects | selected project values only |
| Read-only guarantee | UI inspection | no Approve/Resolve/Accept; no POST |

Do not treat Cloud string tests or `tsc`/`vite build` as authentic Local evidence.
