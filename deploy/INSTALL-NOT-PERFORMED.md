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

## What an operator runs, exactly

Every command below is for a human to run and check. None of them is run here.

### 0. Prerequisites

```bash
ATLAS_ROOT=/srv/atlas                 # or anywhere the service account owns
ATLAS_SERVICE_USER=atlas-dispatcher   # dedicated, unprivileged, NOT your login
PINNED_HEAD=<40-char revision>
```

### 1. Create the account and the separated paths

```bash
sudo useradd --system --home-dir "$ATLAS_ROOT" --shell /usr/sbin/nologin \
    "$ATLAS_SERVICE_USER"
sudo install -d -o "$ATLAS_SERVICE_USER" -g "$ATLAS_SERVICE_USER" -m 0750 \
    "$ATLAS_ROOT"/{checkout,env,programs,registry,state,queue,worktrees,logs,artifacts}
```

`state/` holds checkpoints, events, decisions and leases. **Keep it on local
storage.** Database, leases and locks must never live on SMB; SMB is for
manifests, events and immutable evidence only.

### 2. Pin a non-editable release

```bash
sudo -u "$ATLAS_SERVICE_USER" git clone --no-checkout <REPO> "$ATLAS_ROOT/checkout"
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
```

### 3. Run it in the foreground first — no service yet

This is the step that proves the dispatcher works before anything is made
permanent. It needs no privileges at all.

```bash
sudo -u "$ATLAS_SERVICE_USER" "$ATLAS_ROOT/env/bin/python" \
    -m project_atlas.orchestration.program.cli program dispatcher \
    --state-root "$ATLAS_ROOT/state" --queue-root "$ATLAS_ROOT/queue" \
    --checkout "$ATLAS_ROOT/checkout" --action run \
    --tick-seconds 5 --max-seconds 60
```

Detached, surviving terminal closure, still without a service:

```bash
sudo -u "$ATLAS_SERVICE_USER" setsid nohup "$ATLAS_ROOT/env/bin/python" \
    -m project_atlas.orchestration.program.cli program dispatcher \
    --state-root "$ATLAS_ROOT/state" --queue-root "$ATLAS_ROOT/queue" \
    --checkout "$ATLAS_ROOT/checkout" --action run \
    >> "$ATLAS_ROOT/logs/dispatcher.log" 2>&1 < /dev/null &
```

Then close the terminal and check from a new one:

```bash
"$ATLAS_ROOT/env/bin/python" -m project_atlas.orchestration.program.cli \
    program dispatcher --state-root "$ATLAS_ROOT/state" --action status
```

`alive: true` means the recorded pid is running **under the recorded start
identity**. `alive: null` means nothing could be compared — it is not a yes.

### 4. Install the unit (the authorized-privilege step)

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
"$ATLAS_ROOT/env/bin/python" -m project_atlas.orchestration.program.cli \
    program dispatcher --state-root "$ATLAS_ROOT/state" --action status
```

The heartbeat's `revision_head` must equal `$PINNED_HEAD`. A service that came
back on different code is a fact you need to see here, not discover later.

### 6. Prove failure restart returns the pinned revision

```bash
MAINPID=$(systemctl show -p MainPID --value atlas-resident-dispatcher)
sudo kill -9 "$MAINPID"        # by PID. Never by name, pattern or directory.
sleep 35                        # RestartSec=30
systemctl is-active atlas-resident-dispatcher
# heartbeat pid must differ; revision_head must be unchanged.
```

## VPS portability

Nothing above is host-specific. The layer uses no `inotify`, no D-Bus, no
machine id and no absolute path outside `$ATLAS_ROOT`; task semantics are
carried entirely by the program file, the envelopes and the checkpoints, all of
which are plain JSON under `$ATLAS_ROOT`. Moving to a VPS is: create the
account, clone and pin the same revision, copy `$ATLAS_ROOT/{programs,queue,
state,registry}`, install the unit.

`VPS_PORTABILITY` is therefore **argued, not verified**: no VPS was provisioned
from this session, and an argument from the absence of host dependencies is not
a migration that was performed. It stays `NOT_VERIFIED` until somebody runs it.
