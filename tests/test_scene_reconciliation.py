"""Presence checks distinguish removed scenes from valid rows on older pages."""

import pytest


def create_job(service, tenant_id):
    return service.database.create_job(
        tenant_id=tenant_id,
        engine_id="synthetic-sample-v1",
        source_asset_id=None,
        params={},
        provenance={},
        reserve_units=0,
    )


def test_scene_presence_is_independent_of_the_requested_page(
    authenticated_client, service, tenant_id
):
    older = create_job(service, tenant_id)
    removed = create_job(service, tenant_id)
    newest = create_job(service, tenant_id)
    with service.database.transaction() as connection:
        connection.execute("UPDATE jobs SET state='failed' WHERE id=?", (removed["id"],))
    service.database.queue_delete_job(tenant_id, removed["id"])
    params = [("limit", "1"), ("knownId", older["id"]), ("knownId", removed["id"])]
    response = authenticated_client.get("/api/jobs", params=params)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    page = response.json()
    assert [job["id"] for job in page["jobs"]] == [newest["id"]]
    assert page["missingIds"] == [removed["id"]]
    assert page["nextCursor"]
    following = authenticated_client.get(
        "/api/jobs", params=params + [("cursor", page["nextCursor"])]
    ).json()
    assert [job["id"] for job in following["jobs"]] == [older["id"]]
    assert following["missingIds"] == [removed["id"]]
    assert following["nextCursor"] is None
    assert authenticated_client.get("/api/jobs").json()["missingIds"] == []


def test_scene_presence_does_not_disclose_other_tenants(authenticated_client, service):
    other = service.database.provision_tenant(
        token="scene-presence-other-tenant-token", tenant_name="Other", quota_units=10
    )
    private = create_job(service, other["tenant_id"])
    unknown = "job_" + "f" * 32
    response = authenticated_client.get(
        "/api/jobs", params=[("knownId", private["id"]), ("knownId", unknown)]
    )
    assert response.status_code == 200
    assert response.json() == {
        "jobs": [],
        "nextCursor": None,
        "missingIds": [private["id"], unknown],
    }


@pytest.mark.parametrize("known_ids", [["invalid"], ["job_" + "a" * 32] * 101])
def test_scene_presence_rejects_invalid_or_unbounded_batches(authenticated_client, known_ids):
    response = authenticated_client.get(
        "/api/jobs", params=[("knownId", value) for value in known_ids]
    )
    assert response.status_code == 422


def test_scene_presence_accepts_the_batch_limit_and_deduplicates(authenticated_client):
    ids = [f"job_{index:032x}" for index in range(100)]
    response = authenticated_client.get("/api/jobs", params=[("knownId", value) for value in ids])
    assert response.status_code == 200
    assert response.json()["missingIds"] == ids
    response = authenticated_client.get("/api/jobs", params=[("knownId", ids[0])] * 2)
    assert response.json()["missingIds"] == [ids[0]]


def test_scene_presence_requires_authentication(client):
    response = client.get("/api/jobs", params={"knownId": "job_" + "a" * 32})
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
