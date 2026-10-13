"""Cache only fingerprint-matched, source-controlled public assets long term."""

from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import QueryParams
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from .pages import asset_digest


class VersionedStaticFiles(StaticFiles):
    def current_digest(self, path: str) -> str | None:
        # Use StaticFiles' containment checks, including for symlinks.
        try:
            full_path, info = self.lookup_path(path)
            if info is not None:
                return asset_digest(Path(full_path), info.st_mtime_ns, info.st_size)
        except OSError:
            pass
        return None

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        versions = QueryParams(scope["query_string"]).getlist("v")
        # Raw HTML contains unversioned references and must always revalidate.
        if (
            response.status_code in {200, 304}
            and Path(path).suffix.lower() != ".html"
            and len(versions) == 1
            and versions[0] == await run_in_threadpool(self.current_digest, path)
        ):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
