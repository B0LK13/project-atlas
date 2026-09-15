# ADV pool fixtures (PREP sketches)

Docs-only fixture family for AS-2.2-ADV-POOL-001.

## Policy

See [FIXTURE-INVARIANTS.md](../FIXTURE-INVARIANTS.md).

## Sample negative markers (synthetic only)

These strings are **shape tokens** for authors — not live credentials and not
executable harness inputs in this PREP package:

| Token | Intended use |
|---|---|
| `sk-test-not-a-real-key` | Provider-key *shape* in negative docs |
| `vault-rel://projects/demo/note.md` | Synthetic relative path idiom |
| `evidence_class=fixture` | Explicit non-pilot evidence |

No payload files with secret-like bodies are shipped in this directory yet.
Post-unlock executable ADV may add JSON sketches under sibling package
ownership without promoting RELEASE flags.
