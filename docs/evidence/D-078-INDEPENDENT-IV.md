# D-078 Cloud IV

Implementer Cloud IV against production freeze
`fcaf4f5e152b162a52bfc1c28654ff11acbeb842` /
tree `119c779f8995ab576a231aaa06a334fb813cd737`.

Windows volume roots were simulated on Linux by monkeypatching the
classifiers. Cloud did **not** access authentic `D:\`.

| # | Question | Required | Verdict |
| --- | --- | --- | --- |
| 1 | Does default mode still refuse a Windows volume root? | YES | YES |
| 2 | Does explicit `owner-authorized-volume` accept a non-system Windows volume root? | YES | YES |
| 3 | Does explicit mode still refuse the Windows system volume? | YES | YES |
| 4 | Does home remain refused, including under volume mode? | YES | YES |
| 5 | Does Linux/macOS `/` remain refused, including under volume mode? | YES | YES |
| 6 | Is UNC/network refused as a volume-root exception? | YES | YES |
| 7 | Are external reparse/symlink targets from an authorized volume not followed? | YES | YES |

Additional Cloud IV probes (same session):

| Probe | Verdict |
| --- | --- |
| Normal bounded directory unchanged (`BOUNDED_DIRECTORY`) | PASS |
| Non-root directory + volume mode refused (no silent reinterpret) | PASS |
| API projection exposes mode / volume_root_authorized / kind | PASS |

```
CLOUD_IV = PASS
NEW_HIGH = 0
NEW_SECURITY_HIGH = 0
```

A separate reviewer may re-confirm these seven questions. Local must still
prove them on authentic Windows `D:\` / `C:\` before merge.
