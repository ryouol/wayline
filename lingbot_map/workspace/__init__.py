"""Durable, tenant-scoped workspace for 3D reconstruction jobs.

Import :func:`lingbot_map.workspace.app.create_app` to construct the web app.
Keeping this module dependency-free lets research utilities use checkpoint
verification without importing the FastAPI surface.
"""
