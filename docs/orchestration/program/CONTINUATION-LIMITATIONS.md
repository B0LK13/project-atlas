# Limitations and unresolved risks

Written before independent verification, deliberately. Each item is something a
verifier should be able to confirm is stated here rather than discover.

## Not delivered, and why

| claim the goal asks for | status | why |
| --- | --- | --- |
| `SYSTEM_SERVICE=INSTALLED_ENABLED_REBOOT_VERIFIED` | **NOT_DELIVERED** | needs root, a new system account, and a reboot of a shared host. The directive in force says "Do not install a system service"; standing constraints say sudo and machine-wide service installation are not authorized. The reviewed template and the exact operator procedure are in `deploy/`. |
| reboot recovery | `NOT_VERIFIED` | only a real reboot proves it. Generated configuration is not evidence. |
| `VPS_PORTABILITY=VERIFIED` | **argued, not verified** | the layer uses no `inotify`, no D-Bus, no machine id and no path outside the state root — but no VPS was provisioned, and an argument from absent host dependencies is not a migration that was performed. |
| `INDEPENDENT_VERDICT=PASS` | `PENDING` | I implemented this. I am disqualified from verifying it. |

## Stated limits of what was proven

**Fixture adapters only.** `FIXTURE_RUN != REAL_RUNTIME_COMPATIBILITY`. The
Claude Code and Codex adapters still load and validate; neither was launched.
Nothing here establishes that a real runtime's cancellation, rate-limiting or
unparseable result flows through this layer the way the fixture's does.

**"Efficient waiting" is bounded polling, not a blocking primitive.** One
`stat` per wake quantum (default 0.5 s) and one queue read per tick (default
5 s). It is not `inotify` and the module says so. The test measures CPU over a
real idle hold rather than trusting the description — but a machine under heavy
load could still see a longer wake latency than the quantum suggests.

**The zero-network proof covers this interpreter only.** The socket ban in
`test_the_whole_layer_makes_zero_model_calls_and_opens_no_socket` applies to
the process running the dispatcher, the reconciler and the capsule. It does not
instrument the fixture child process; instead the test asserts the child's argv
is the local fixture worker, which opens nothing. A different adapter would
need its own proof.

**Concurrency is not exercised by this layer's tests.** The dispatcher runs one
program at a time and the supervisor's own concurrency is covered by the
pre-existing suite. Two dispatchers against one state root are not tested and
not supported: nothing in this layer takes a cross-dispatcher singleton lock.

**Clock trust.** Deadlines and lease expiry are compared against the local
clock. A host whose clock jumps backwards can make an expired lease look live
and a passed deadline look future. There is no monotonic durable clock here,
and the registry host in this program is already known to run ~59 minutes fast.

**Python 3.14 is outside the supported matrix, and it is not clean.** Built
against Python 3.12 (`pyproject.toml` targets 3.12; CI runs 3.12 and 3.13). A
3.14.4 environment fails five PRE-EXISTING tests in
`test_discovery_error_policy.py` and `test_linux_filesystem_portability.py`.
Established as pre-existing by a matched control: the same five fail on the
pristine base commit `250eb1cb` in the same environment with every change of
mine stashed, and all five pass on 3.12 with the changes applied. It is a real
finding about the repository on 3.14, and it is not this layer's.

**Windows is untested for this layer.** The code avoids POSIX-only calls and
reuses the package's existing cross-platform identity helpers, but every test
here ran on Linux. `resource.getrusage` in the idle-waiting test is POSIX-only
and that test would need a different oracle on Windows.

## Open risks carried in from the program

* **R-12 open.** Cleanup by process identity in a shared session. This layer
  never kills by name, pattern or working directory, and its own tests assert
  that property against their source — but R-12 is not closed by that.
* **R-13 open.**
* **`MODEL_BACKED_DISPATCH=DISABLED`** until R-12 closes *and* this layer has
  independent verification.

## Things a verifier should specifically try to break

1. Delete a terminal checkpoint and check whether completed work becomes
   replayable. It should — that is the documented single point of failure for
   the no-replay guarantee, and the rollback procedure says not to do it.
2. Run two dispatchers against one state root. Nothing stops you; nothing
   claims it is safe.
3. Set the host clock backwards and re-run the stale-lease test.
4. Hand the capsule a state root with 500 envelopes and check that every
   truncation is announced.
5. ~~Corrupt `approved-work-queue.json`~~ — raised here, then defended:
   `test_a_corrupt_queue_is_reported_and_never_looks_like_an_empty_one` asserts
   the dispatcher reports `WAITING_ON_WORK`, not `IDLE_EMPTY_QUEUE`. Try to
   find the version of this that is still collapsed somewhere else.
