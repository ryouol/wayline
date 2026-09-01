"""Compatibility launcher for the packaged 3D Scene Workspace.

Prefer the installed ``lingbot-workspace`` command. For local development:

    python webui/server.py --dev
"""

from lingbot_map.workspace.app import main

if __name__ == "__main__":
    main()
