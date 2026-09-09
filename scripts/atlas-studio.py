#!/usr/bin/env python3
"""atlas-studio entry point (AS-STUDIO-A0-001).

STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
STUDIO_CRASH != AGENT_TASK_TERMINATION
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from atlas_studio.cli import main

if __name__ == "__main__":
    sys.exit(main())
