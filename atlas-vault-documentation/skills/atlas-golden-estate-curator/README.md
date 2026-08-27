# Atlas Golden Estate Curator

Reusable Atlas skill that **discovers and qualifies** development projects
for future acceptance-test estates.

It is not Truth Core. It does not copy, move, or goldenize anything unless a
later owner-authorized package implements those phases.

## Default mode

`DISCOVER_ONLY`. Source trees are evidence.

```bash
python curator.py --source-root /path/to/projects --phase RECOMMEND \
  --output /tmp/estate-report.json
```

## Certification (cloud / Linux fixtures)

Synthetic fixture estate + unit + adversarial tests in `tests/`.

Authentic `D:\` discovery remains `LOCAL_WINDOWS_REQUIRED`.
See `references/WINDOWS-D-DRIVE.md`.
