# Installation: prepared, not performed

`SYSTEM_SERVICE = NOT_INSTALLED` · `REBOOT_RECOVERY = NOT_VERIFIED`

The goal `ATLAS-PERSISTENT-AUTONOMOUS-SUPERVISOR-001` asks for
`SYSTEM_SERVICE=INSTALLED_ENABLED_REBOOT_VERIFIED`. That is **not delivered
here**, and it is not delivered because it cannot be honestly claimed from this
session, not because it was skipped:

* the directive in force says, verbatim, *"Do not install a system service.
  Deliver a reviewed but uninstalled startup template and exact manual
  foreground/detached commands."*
* standing constraints say *"Sudo, machine-wide service installation and
  `loginctl enable-linger` are not authorized."*
* creating a dedicated unprivileged account, writing to `/etc/systemd/system`,
  and rebooting a shared host each need privileges this process does not hold.

A reboot is also the only proof of reboot recovery. Generated configuration is
not evidence, and this file does not pretend it is.

## Prepared operator procedure — not executed here

Every command below is for an authorized operator to review and run. None is
run as part of this documentation change. Parsing command construction does
not install a service, validate its runtime sandbox, or prove reboot recovery.
Local-command fixture and supervised-process restart tests exercise a narrower
chain; they are not service-manager or host-reboot evidence.

### 0. Prerequisites

```bash
ATLAS_ROOT=/srv/atlas                 # explicit approved boundary, not / or HOME
ATLAS_SERVICE_USER=atlas-dispatcher   # dedicated, unprivileged, NOT your login
PINNED_HEAD='REPLACE_WITH_APPROVED_40_CHARACTER_REVISION'
REPO='REPLACE_WITH_APPROVED_REPOSITORY_URL'
```

Use an absolute root with no symlink/reparse components. For this unquoted unit
template and its substitution command, restrict the root to letters, digits,
`/`, `_`, `-` and `.` (no `..` components); do not use whitespace or expansion
characters. The account's home must be **different** from ATLAS_ROOT because
the guard refuses the current account's home as a governed root.

The layout is explicitly governed, not inferred from a common ancestor:

```text
/srv/atlas/                 --governed-root
    checkout/              pinned runtime source, read-only to service
    env/                   noneditable installed package
    programs/approved.json operator-approved program bytes
    registry/              explicit absolute enrollment binding
    state/                 --state-root (never inside a worker workspace)
    queue/                 --queue-root
    worktrees/task/        approved task workspace
    logs/
    artifacts/
```

All commands below retain the explicit root. The fail-closed state-root default
does not permit its sibling queue/program/workspace paths. A registry may be a
separate explicitly trusted absolute root; this example keeps it under G.

### 1. Create the account and the separated paths

```bash
sudo useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin \
    "$ATLAS_SERVICE_USER"
sudo install -d -o "$ATLAS_SERVICE_USER" -g "$ATLAS_SERVICE_USER" -m 0750 \
    "$ATLAS_ROOT"/{checkout,env,programs,registry,state,queue,worktrees,logs,artifacts}
```

`state/` holds checkpoints, events, decisions and leases. **Keep it on local
storage.** Database, leases and locks must never live on SMB; SMB is for
manifests, events and immutable evidence only.

### 2. Pin a non-editable release

```bash
sudo -u "$ATLAS_SERVICE_USER" git clone --no-checkout "$REPO" "$ATLAS_ROOT/checkout"
sudo -u "$ATLAS_SERVICE_USER" git -C "$ATLAS_ROOT/checkout" checkout "$PINNED_HEAD"
sudo -u "$ATLAS_SERVICE_USER" python3 -m venv "$ATLAS_ROOT/env"
# NON-editable on purpose: an editable install resolves through a working tree.
sudo -u "$ATLAS_SERVICE_USER" "$ATLAS_ROOT/env/bin/pip" install "$ATLAS_ROOT/checkout"
```

Verify the pin before going further:

```bash
git -C "$ATLAS_ROOT/checkout" rev-parse HEAD          # must equal $PINNED_HEAD
git -C "$ATLAS_ROOT/checkout" rev-parse 'HEAD^{tree}'
git -C "$ATLAS_ROOT/checkout" status --porcelain      # must be empty
"$ATLAS_ROOT/env/bin/python" -I -c 'import project_atlas; print(project_atlas.__file__)'
```

The module path must be inside the pinned environment's `site-packages`, not
the source checkout. Record package/revision provenance together; a checkout
heartbeat alone does not prove which installed module the interpreter imported.

### 3. Run it in the foreground first — no service yet

First provide approved program bytes, an actual pinned task worktree and active
registry assignments for that exact program. An empty queue only proves waiting,
not worker execution. Admission is an explicit operator act, not discovery:

```bash
sudo -u "$ATLAS_SERVICE_USER" "$ATLAS_ROOT/env/bin/python" \
    -m project_atlas.orchestration.program.cli program queue \
    --governed-root "$ATLAS_ROOT" --queue-root "$ATLAS_ROOT/queue" \
    --state-root "$ATLAS_ROOT/state" --action admit \
    --program "$ATLAS_ROOT/programs/approved.json" \
    --admitted-by 'REPLACE_WITH_OPERATOR_ID' --reference 'REPLACE_WITH_APPROVAL_REFERENCE'
```

The foreground command is an actual execution command when run with approved
queued work. It is not a dry run. Invoking it as the already-provisioned service
account needs no service installation; the `sudo -u` wrapper below separately
requires permission to switch to that account.

```bash
sudo -u "$ATLAS_SERVICE_USER" "$ATLAS_ROOT/env/bin/python" \
    -m project_atlas.orchestration.program.cli program dispatcher \
    --governed-root "$ATLAS_ROOT" \
    --state-root "$ATLAS_ROOT/state" --queue-root "$ATLAS_ROOT/queue" \
    --checkout "$ATLAS_ROOT/checkout" --registry "$ATLAS_ROOT/registry" --action run \
    --tick-seconds 5 --max-seconds 60
```

Detached command to test terminal-closure survival, still without a service.
Observe the result from another terminal; detachment syntax alone is not proof:

```bash
sudo -u "$ATLAS_SERVICE_USER" setsid nohup "$ATLAS_ROOT/env/bin/python" \
    -m project_atlas.orchestration.program.cli program dispatcher \
    --governed-root "$ATLAS_ROOT" \
    --state-root "$ATLAS_ROOT/state" --queue-root "$ATLAS_ROOT/queue" \
    --checkout "$ATLAS_ROOT/checkout" --registry "$ATLAS_ROOT/registry" --action run \
    >> "$ATLAS_ROOT/logs/dispatcher.log" 2>&1 < /dev/null &
```

Then close the terminal and check from a new one:

```bash
sudo -u "$ATLAS_SERVICE_USER" "$ATLAS_ROOT/env/bin/python" -m project_atlas.orchestration.program.cli \
    program dispatcher --governed-root "$ATLAS_ROOT" --state-root "$ATLAS_ROOT/state" --action status
```

`alive: true` means the recorded pid is running **under the recorded start
identity**. `alive: null` means nothing could be compared — it is not a yes.

### 4. Install the unit (the authorized-privilege step)

**Preparation is not activation-ready proof.** The template's `ExecStop` sends
a drain request and immediately returns; it does not wait for identity-checked
dispatcher/worker exit. Review a bounded synchronous stop/wait hook before
enabling unattended in-flight shutdown, or drain and observe exit explicitly
before stopping the unit. `TimeoutStopSec` alone does not supply this hook.
Do not run the installation/activation commands below until that operational
choice, privileges, unit validation and local foreground checks are approved.
Ensure no foreground/detached dispatcher still owns the same state root.

```bash
sed -e "s|<ATLAS_ROOT>|$ATLAS_ROOT|g" \
    -e "s|<ATLAS_SERVICE_USER>|$ATLAS_SERVICE_USER|g" \
    -e "s|<ATLAS_SERVICE_GROUP>|$ATLAS_SERVICE_USER|g" \
    "$ATLAS_ROOT/checkout/deploy/atlas-resident-dispatcher.service.template" \
    | sudo tee /etc/systemd/system/atlas-resident-dispatcher.service
sudo systemd-analyze verify /etc/systemd/system/atlas-resident-dispatcher.service
sudo systemctl daemon-reload
sudo systemctl enable --now atlas-resident-dispatcher
```

### 5. Prove reboot recovery — the part only a reboot can prove

```bash
sudo reboot
# after it comes back:
systemctl is-enabled atlas-resident-dispatcher    # enabled
systemctl is-active  atlas-resident-dispatcher    # active
sudo -u "$ATLAS_SERVICE_USER" "$ATLAS_ROOT/env/bin/python" -m project_atlas.orchestration.program.cli \
    program dispatcher --governed-root "$ATLAS_ROOT" --state-root "$ATLAS_ROOT/state" --action status
```

Record boot identity before/after, the new process PID/start identity, installed
module provenance, HEAD/TREE, recovered pause/uncertain state and zero replay of
completed tasks. `is-active` alone is not a recovery proof. The heartbeat's
`revision_head` must equal `$PINNED_HEAD`; compare TREE too.

### 6. Prove failure restart returns the pinned revision

This is a separately authorized destructive fault test, not part of setup or
this documentation change. Use an approved disposable instance and an
identity-aware helper: corroborate the unit's MainPID with the recorded process
start identity immediately before signalling. A bare PID copied from an earlier
status read is insufficient. Capture pre/post witnesses and verify new identity,
same pinned revision/module, no leaked owned worker and no repeated completed or
uncertain effect. No failure signal or service restart was performed here.

## Separate finite-service scope

This procedure uses `program dispatcher`, not `program service install/start/run`.
The finite-service helpers now carry explicit `governed_root` through loading,
generated launcher/child argv and supervisor construction. Supply it for sibling
program/state/worktree layouts; the default remains the program file's directory.
Construction tests mock installation and launch sinks, not an actual service.
Do not substitute the finite-service launcher for this resident template or
weaken containment. Activation and reboot remain separately unverified.

## VPS portability

This startup template targets a Linux systemd host; it is not a portable service
installer. Records include absolute program/workspace/state/registry paths, so
copying JSON to a new root is not automatic relocation or migration. Preserve
bindings and compatible readers, or obtain a separate reviewed migration. See
[Migration and rollback](../docs/orchestration/program/CONTINUATION-MIGRATION-AND-ROLLBACK.md).

`VPS_PORTABILITY = NOT_VERIFIED`: no VPS was provisioned or migration performed.
Service/reboot/failure-restart claims remain unverified until independently
observed on the approved installed revision. Do not reuse local fixture results
as those verdicts.
