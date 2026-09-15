# Project discovery contract

Discovery accepts an explicit project root or scans a bounded workspace without
following directory symlinks. An explicit root is authoritative; workspace
projects require a marker. `.atlas-project.yaml` supplies canonical identity,
authority rules, and discovery policy. Unsafe or invalid manifests fail closed.
