# Safety contract

Source projects are evidence.

Fail closed on:

- MOVE / DELETE / RENAME / SOURCE_MODIFY
- GIT_CLEAN / GIT_RESET / HISTORY_REWRITE
- AUTO_COMMIT / AUTO_PUSH / AUTO_MERGE
- COPY / GOLDENIZE without a later owner-authorized implementation
- UNC paths
- path traversal (`..`)
- symlink / junction escape
- report output written inside the source root
- execution of project test or build scripts

Secrets: record pattern metadata only. Never echo matched content.
