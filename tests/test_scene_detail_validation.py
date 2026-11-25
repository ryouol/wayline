"""Detail validation must observe artifacts and authorize every request."""

import pytest

from .conftest import BOOTSTRAP_TOKEN


def ready_scene(client, service):
    job = client.post("/api/jobs/sample").json()
    assert service.process_next_job()
    return f"/api/jobs/{job['id']}"


@pytest.mark.parametrize("condition", ["exact", "weak", "list", "wildcard"])
def test_unchanged_detail_has_no_body(authenticated_client, service, condition):
    client = authenticated_client
    url = ready_scene(client, service)
    first = client.get(url)
    etag = first.headers["etag"]
    match = {"exact": etag, "weak": "W/" + etag, "list": '"old", ' + etag, "wildcard": "*"}
    response = client.get(url, headers={"If-None-Match": match[condition]})
    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == etag
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-workspace-principal"] == first.headers["x-workspace-principal"]
    assert client.get(url, headers={"If-None-Match": '"stale"'}).json() == first.json()


def test_artifact_cleanup_invalidates_unchanged_job(authenticated_client, service, tenant_id):
    client = authenticated_client
    url = ready_scene(client, service)
    first = client.get(url)
    job = first.json()
    assert job["artifacts"]
    current = service.database.get_artifact(tenant_id, job["artifacts"][0]["id"])
    assert service.database.queue_attempt_artifacts(
        tenant_id, job["id"], attempt_token=current["attempt_token"]
    )
    response = client.get(url, headers={"If-None-Match": first.headers["etag"]})
    assert response.status_code == 200
    assert response.headers["etag"] != first.headers["etag"]
    assert response.json()["updatedAt"] == job["updatedAt"]
    assert response.json()["artifacts"] == []
    service.database.queue_delete_job(tenant_id, job["id"])
    assert client.get(url, headers={"If-None-Match": response.headers["etag"]}).status_code == 404


def test_detail_and_deadline_changes_invalidate(authenticated_client, service):
    client = authenticated_client
    url = ready_scene(client, service)
    first = client.get(url)
    with service.database.transaction() as connection:
        connection.execute(
            "UPDATE jobs SET finished_at=finished_at+10 WHERE id=?", (first.json()["id"],)
        )
    second = client.get(url, headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 200
    assert second.headers["etag"] != first.headers["etag"]
    assert second.json()["expiresAt"] == first.json()["expiresAt"] + 10


def test_validation_never_bypasses_tenant_or_session_checks(authenticated_client, service):
    client = authenticated_client
    url = ready_scene(client, service)
    etag = client.get(url).headers["etag"]
    service.database.provision_tenant(
        token="another-tenant-token-with-enough-length", tenant_name="Other", quota_units=10
    )
    response = client.get(
        url,
        headers={
            "If-None-Match": etag,
            "Authorization": "Bearer another-tenant-token-with-enough-length",
        },
    )
    assert response.status_code == 404
    response = client.get(url, headers={"If-None-Match": etag, "Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    # A valid bearer still revalidates normally after rejected credentials.
    assert (
        client.get(
            url, headers={"If-None-Match": etag, "Authorization": f"Bearer {BOOTSTRAP_TOKEN}"}
        ).status_code
        == 304
    )
