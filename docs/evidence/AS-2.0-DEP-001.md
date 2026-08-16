# AS-2.0-DEP-001 — Evidence-backed project dependencies

Only explicit dependency claims become edges.

Never inferred from:

- shared words
- shared files
- similar technology
- simultaneous changes
- same source owner

`DEPENDENCY_IS_INFERRED = NO` unless the claim itself is an explicit
`dependency_candidate` class. That class is still evidenced, not inferred.

`DEPENDENCY ≠ INFERRED / ≠ SHARED-VOCABULARY EDGE`
