from __future__ import annotations

import pytest


def _capture_job(client, service, tenant_id, filename):
    upload = client.post(
        "/api/assets",
        files={"file": (filename, b"\x00\x00\x00\x18ftypisom" + b"\x00" * 52, "video/mp4")},
    )
    assert upload.status_code == 201
    return service.database.create_job(
        tenant_id=tenant_id,
        engine_id="lingbot-research-v1",
        source_asset_id=upload.json()["id"],
        params={},
        provenance={},
        reserve_units=0,
    )


def test_scene_names_remain_consistent_across_details_and_cursor_pages(
    authenticated_client, service, tenant_id
):
    expected = {}
    for filename, display_name in (
        ("Living_room.take_2.MP4", "Living room.take 2"),
        ("Office   walkthrough.mp4", "Office walkthrough"),
        ("Garden-2026.mp4", "Garden-2026"),
    ):
        job = _capture_job(authenticated_client, service, tenant_id, filename)
        expected[job["id"]] = display_name

    sample = authenticated_client.post("/api/jobs/sample")
    assert sample.status_code == 202
    assert sample.json()["displayName"] == "Synthetic studio"
    expected[sample.json()["id"]] = "Synthetic studio"

    # Equal timestamps exercise the id tie-breaker while the asset join is present.
    with service.database.transaction() as connection:
        connection.execute("UPDATE jobs SET created_at = 1000 WHERE tenant_id = ?", (tenant_id,))
    found = {}
    params = {"limit": 2}
    while True:
        response = authenticated_client.get("/api/jobs", params=params)
        assert response.status_code == 200
        page = response.json()
        for job in page["jobs"]:
            assert job["id"] not in found
            found[job["id"]] = job["displayName"]
            detail = authenticated_client.get(f"/api/jobs/{job['id']}")
            assert detail.status_code == 200
            assert detail.json()["displayName"] == job["displayName"]
            assert "source_original_name" not in detail.json()
        if not page["nextCursor"]:
            break
        params = {"limit": 2, "cursor": page["nextCursor"]}
    assert found == expected
    assert {job["id"] for job in service.database.list_jobs(tenant_id)} == expected.keys()


def test_scene_names_never_read_another_tenants_source(authenticated_client, service, tenant_id):
    own_job = _capture_job(authenticated_client, service, tenant_id, "My_room.mp4")
    other = service.database.provision_tenant(
        token="other-scene-name-tenant-token", tenant_name="Other", quota_units=10
    )
    asset = service.database.create_asset(
        tenant_id=other["tenant_id"],
        object_key=f"{other['tenant_id']}/private.mp4",
        original_name="Private_customer_capture.mp4",
        media_type="video/mp4",
        size_bytes=64,
        sha256="0" * 64,
        metadata={},
    )
    other_job = service.database.create_job(
        tenant_id=other["tenant_id"],
        engine_id="lingbot-research-v1",
        source_asset_id=asset["id"],
        params={},
        provenance={},
        reserve_units=0,
    )
    assert authenticated_client.get(f"/api/jobs/{other_job['id']}").status_code == 404
    with pytest.raises(KeyError):
        service.database.create_job(
            tenant_id=tenant_id,
            engine_id="lingbot-research-v1",
            source_asset_id=asset["id"],
            params={},
            provenance={},
            reserve_units=0,
        )

    # Even an inconsistent foreign source reference cannot disclose its filename.
    with service.database.transaction() as connection:
        connection.execute(
            "UPDATE jobs SET source_asset_id = ? WHERE id = ?", (asset["id"], own_job["id"])
        )
    detail = authenticated_client.get(f"/api/jobs/{own_job['id']}").json()
    assert detail["displayName"] == "Captured space"
    page = authenticated_client.get("/api/jobs").json()
    assert [(job["id"], job["displayName"]) for job in page["jobs"]] == [
        (own_job["id"], "Captured space")
    ]
    assert service.database.list_jobs(tenant_id)[0]["source_original_name"] is None


def test_scene_without_source_keeps_a_useful_name(authenticated_client, service, tenant_id):
    job = service.database.create_job(
        tenant_id=tenant_id,
        engine_id="lingbot-research-v1",
        source_asset_id=None,
        params={},
        provenance={},
        reserve_units=0,
    )
    detail = authenticated_client.get(f"/api/jobs/{job['id']}")
    assert detail.status_code == 200
    assert detail.json()["displayName"] == "Captured space"
