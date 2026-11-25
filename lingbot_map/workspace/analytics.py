"""Optional first-party counts; no visitors, sessions or external forwarding."""

import argparse
import json
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .database import Database


class PageView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    propertyId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    event: Literal["page_view"]
    page: Literal["/", "/privacy", "/terms", "/contact"]


def register_analytics_routes(app: FastAPI, database: Database, settings: Settings, limiter):
    @app.post("/analytics/page-view", status_code=204, include_in_schema=False)
    def collect(payload: PageView, request: Request):
        if not settings.analytics_enabled:
            raise HTTPException(404, "Analytics is disabled.")
        expected = settings.public_base_url or str(request.base_url).rstrip("/")
        if (
            request.headers.get("origin") != expected
            or request.headers.get("sec-fetch-site") not in (None, "same-origin")
            or request.headers.get("x-wayline-analytics-consent") != "accepted"
            or request.headers.get("dnt") == "1"
            or request.headers.get("sec-gpc") == "1"
        ):
            raise HTTPException(403, "Analytics consent and same-origin access are required.")
        if payload.propertyId != settings.analytics_property_id:
            raise HTTPException(422, "Unknown analytics property.")
        # Public ingestion has no private reads. A global bucket stores no client identity.
        if not limiter.allow("analytics"):
            raise HTTPException(429, "Analytics rate limit reached.", headers={"Retry-After": "60"})
        day = int(time.time() // 86400)
        with database.transaction() as connection:
            connection.execute("DELETE FROM analytics_daily WHERE day < ?", (day - 29,))
            total = connection.execute(
                "SELECT COALESCE(SUM(views),0) FROM analytics_daily WHERE day=?", (day,)
            ).fetchone()[0]
            if total >= 10_000:
                raise HTTPException(429, "Analytics daily count limit reached.")
            connection.execute(
                "INSERT INTO analytics_daily(day,page,views) VALUES(?,?,1) "
                "ON CONFLICT(day,page) DO UPDATE SET views=views+1",
                (day, payload.page),
            )
        return Response(status_code=204, headers={"Cache-Control": "no-store"})


def aggregate_report(data_dir: Path) -> dict:
    """Read only: UTC daily page totals from this workspace, never unique visitors."""
    day = int(time.time() // 86400)
    path = (data_dir / "workspace.sqlite3").resolve()
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
        rows = connection.execute(
            "SELECT day,page,views FROM analytics_daily WHERE day BETWEEN ? AND ? "
            "ORDER BY day,page",
            (day - 29, day),
        ).fetchall()
    return {
        "retentionDays": 30,
        "counts": [
            {
                "day": datetime.fromtimestamp(value * 86400, UTC).date().isoformat(),
                "page": page,
                "views": views,
            }
            for value, page, views in rows
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Read Wayline's last 30 UTC days of page totals")
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(aggregate_report(args.data_dir), indent=2))


if __name__ == "__main__":
    main()
