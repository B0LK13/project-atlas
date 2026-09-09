"""Atlas Studio — A0 snapshot + A1 Mission Control + A2 governance substrate.

STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
NO_WHOLESALE_CORE_REWRITE
REUSE_BEFORE_REIMPLEMENT
MODEL_PROVIDER != ATLAS_ARCHITECTURE
STUDIO_CRASH != AGENT_TASK_TERMINATION
ATTENTION != AUTHORIZATION
STALE != CURRENT
UNKNOWN != HEALTHY
REQUESTED != CLAIMED
PREVIEW != EXECUTION

Package root remains free of mutation helpers. Reusable governance loop lives
in ``atlas_studio.governance``; OWNERSHIP_CLAIM is the first registered
instance (``atlas_studio.action_intent`` / claim-* CLI) after control-plane
revalidation. Interface never becomes the source of authority.
"""

__version__ = "0.3.0"

# Honesty design laws (must remain True; mirrored in snapshot/MC honesty blocks).
STUDIO_UI_NE_AUTHORITY = True
ATLAS_DAEMON_IS_AUTHORITATIVE_RUNTIME = True
UI_STATE_IS_PROJECTION = True
NO_CLI_TEXT_PARSING_AS_PROTOCOL = True
NO_WHOLESALE_CORE_REWRITE = True
REUSE_BEFORE_REIMPLEMENT = True
MODEL_PROVIDER_NE_ATLAS_ARCHITECTURE = True
STUDIO_CRASH_NE_AGENT_TASK_TERMINATION = True
GRANTS_NO_MUTATION = True
ATTENTION_NE_AUTHORIZATION = True
STALE_NE_CURRENT = True
UNKNOWN_NE_HEALTHY = True
NESTED_HONESTY_FAIL_CLOSED = True
O1_IN_PROCESS_ATLAS_DAG_RO_RUNTIME = True
O6_SEAL_EVIDENCE_MAY_BE_UNKNOWN = True
# A2 honesty consts live on atlas_studio.action_intent (not package root):
# REQUESTED_NE_CLAIMED / PREVIEW_NE_EXECUTION — keep root free of mutation API names.
