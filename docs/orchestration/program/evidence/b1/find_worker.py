"""Find the fixture worker by argv, never by a substring of anyone's shell line.

`pgrep -f` matches the watcher's own command line -- observed in this session --
so this reads /proc/<pid>/cmdline and requires the fixture script to be an
actual argv element of a python process.
"""
import os, sys, pathlib
fixture = sys.argv[1]
me = {os.getpid(), os.getppid()}
for entry in pathlib.Path("/proc").iterdir():
    if not entry.name.isdigit() or int(entry.name) in me:
        continue
    try:
        argv = (entry / "cmdline").read_bytes().split(b"\0")
    except OSError:
        continue
    parts = [a.decode("utf-8", "replace") for a in argv if a]
    if len(parts) >= 2 and fixture in parts[1:] and "python" in pathlib.Path(parts[0]).name:
        print(entry.name)
        break
