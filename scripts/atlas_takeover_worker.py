"""Bounded zero-model worker used only by the local acceptance demonstration."""

import json
import os
import time
from pathlib import Path

task = os.environ["ATLAS_PROGRAM_TASK"]
assert task in {"first", "second"}
with Path(f"{task}.txt").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"task": task, "pid": os.getpid()}) + "\n")
# Let the operator observe the result and request a pause before this process
# exits. The fixture is bounded and never waits for an external service.
time.sleep(0.5)
print(json.dumps({"fixture": True, "task": task, "result": "written"}))
