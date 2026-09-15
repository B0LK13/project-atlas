# D-067 validation commands

Production freeze (Local target):

```
HEAD = ccacaa5bcb094f35017c7195264fef55e382cb49
TREE = d26768fe753c888cd45001987da2afe977c79d45
```

Repro on old candidate `0509287` (before mutation):

```
HIGH_1_CACHE_REPRO = PASS
HIGH_2_DEPTH_REPRO = PASS
```

After remediation:

```
pytest D-049/D-063/D-064/D-067 focused → 46 passed
pytest identity/connect/copied-UUID → 46 passed
pytest coder_alpha|d049|connect|source_identity → passed (1 skipped)
pytest atlas-vault-documentation/tests → 171 passed
ruff / mypy / tsc -b / npm run build → pass
```

CI on exact `ccacaa5` run 31779400311: SUCCESS (ubuntu 3.12 full, ubuntu 3.13 compat, windows 3.12, control-plane).
