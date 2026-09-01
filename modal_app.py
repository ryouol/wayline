"""Inert release manifest for the optional LingBot Modal research runner.

The production workspace never imports the opt-in runner module.  Keeping this
module limited to immutable values makes the disabled release mode auditable:
importing it cannot load the Modal SDK, create an app, allocate volumes, build an
image, register a GPU function, or expose a local entrypoint.

Enabling the research runner requires a reviewed source change to the compile
gate below and an explicit deployment of ``modal_enabled.py``.  No environment
variable or import of this release manifest can enable remote execution.
"""

from __future__ import annotations

LINGBOT_RESEARCH_RUNNER_COMPILED: bool = False
RESEARCH_RUNNER_MODULE = "modal_enabled"
DISABLED_REASON = (
    "Modal research execution is not compiled into this release; owner budget, "
    "cancellation, object-integration, and paid-GPU gates remain open."
)

__all__ = (
    "DISABLED_REASON",
    "LINGBOT_RESEARCH_RUNNER_COMPILED",
    "RESEARCH_RUNNER_MODULE",
)
