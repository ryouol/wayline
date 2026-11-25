import json
import subprocess
import sys
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from lingbot_map.workspace import analytics
from lingbot_map.workspace.app import create_app

EVENT = {"propertyId": "wayline_test", "event": "page_view", "page": "/"}
HEADERS = {"Origin": "http://testserver", "X-Wayline-Analytics-Consent": "accepted"}


def emit(client, **values):
    return client.post("/analytics/page-view", json=EVENT | values, headers=HEADERS)


@pytest.fixture
def enabled_client(settings, service):
    runtime = replace(settings, analytics_enabled=True, analytics_property_id="wayline_test")
    with TestClient(create_app(runtime, service=service, start_worker=False)) as client:
        yield client


def test_disabled_by_default_and_property_requires_operator_input(client, settings):
    assert client.get("/api/config").json()["analytics"] is None
    assert emit(client).status_code == 404
    assert analytics.aggregate_report(settings.data_dir)["counts"] == []
    for value in ("", "https://collector.invalid", "label with spaces", "x" * 65):
        with pytest.raises(ValueError, match="Analytics requires"):
            replace(settings, analytics_enabled=True, analytics_property_id=value).validate()


def test_configured_collector_and_read_only_cli_report(enabled_client, service, settings):
    assert enabled_client.get("/api/config").json()["analytics"] == {
        "propertyId": "wayline_test",
        "endpoint": "/analytics/page-view",
    }
    assert emit(enabled_client, page="/privacy").status_code == 204
    assert emit(enabled_client, page="/privacy").status_code == 204
    response = enabled_client.post(
        "/analytics/page-view",
        json=EVENT,
        headers=HEADERS
        | {
            "Cookie": "session=private-cookie",
            "Authorization": "Bearer private-token",
            "Referer": "https://testserver/s#private-share",
            "X-Forwarded-For": "192.0.2.1",
        },
    )
    assert response.status_code == 204 and response.headers["cache-control"] == "no-store"
    with service.database.connect() as connection:
        assert [row[1] for row in connection.execute("PRAGMA table_info(analytics_daily)")] == [
            "day",
            "page",
            "views",
        ]
        old = int(analytics.time.time() // 86400) - 30
        connection.execute("INSERT INTO analytics_daily VALUES(?, '/contact', 9)", (old,))
    before = service.database.path.read_bytes()
    report = subprocess.run(
        [
            sys.executable,
            "-m",
            "lingbot_map.workspace.analytics",
            "--data-dir",
            str(settings.data_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    counts = json.loads(report.stdout)["counts"]
    assert [(item["page"], item["views"]) for item in counts] == [("/", 1), ("/privacy", 2)]
    assert service.database.path.read_bytes() == before
    with service.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM analytics_daily").fetchone()[0] == 3
    service.run_retention()
    with service.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM analytics_daily").fetchone()[0] == 2


@pytest.mark.parametrize(
    "header,value",
    [
        ("Origin", ""),
        ("Origin", "https://other.invalid"),
        ("Sec-Fetch-Site", "cross-site"),
        ("X-Wayline-Analytics-Consent", ""),
        ("DNT", "1"),
        ("Sec-GPC", "1"),
    ],
)
def test_consent_origin_and_privacy_signals_reject_collection(
    enabled_client, settings, header, value
):
    response = enabled_client.post(
        "/analytics/page-view", json=EVENT, headers=HEADERS | {header: value}
    )
    assert response.status_code == 403
    assert analytics.aggregate_report(settings.data_dir)["counts"] == []


@pytest.mark.parametrize(
    "values",
    [
        {"page": "/s"},
        {"page": "/api/jobs/private"},
        {"page": "/?token=private"},
        {"page": "/#private"},
        {"filename": "private.mp4"},
        {"event": "scene_view"},
        {"propertyId": "unconfigured"},
        {"page": 1},
    ],
)
def test_strict_public_event_schema(enabled_client, settings, values):
    assert emit(enabled_client, **values).status_code == 422
    assert analytics.aggregate_report(settings.data_dir)["counts"] == []


def test_declared_and_streamed_body_limits(enabled_client, settings):
    for body in (b"x" * 513, iter([b"x" * 256, b"x" * 257])):
        response = enabled_client.post(
            "/analytics/page-view",
            content=body,
            headers=HEADERS | {"Content-Type": "application/json"},
        )
        assert response.status_code == 413
    assert analytics.aggregate_report(settings.data_dir)["counts"] == []


def test_global_rate_limit_uses_no_visitor_key(enabled_client, settings):
    for _ in range(120):
        assert emit(enabled_client).status_code == 204
    assert emit(enabled_client).status_code == 429
    assert analytics.aggregate_report(settings.data_dir)["counts"][0]["views"] == 120


def test_retention_and_daily_ceiling_survive_restart(
    enabled_client, settings, service, monkeypatch
):
    day = int(analytics.time.time() // 86400)
    for offset in range(35):
        monkeypatch.setattr(analytics.time, "time", lambda value=day + offset: value * 86400)
        assert emit(enabled_client).status_code == 204
    with service.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM analytics_daily").fetchone()[0] == 30
        connection.execute("UPDATE analytics_daily SET views=9999 WHERE day=?", (day + 34,))
    assert emit(enabled_client).status_code == 204
    assert emit(enabled_client, page="/terms").status_code == 429
    runtime = replace(settings, analytics_enabled=True, analytics_property_id="wayline_test")
    with TestClient(create_app(runtime, service=service, start_worker=False)) as restarted:
        assert emit(restarted).status_code == 429
    assert analytics.aggregate_report(settings.data_dir)["counts"][-1]["views"] == 10_000
