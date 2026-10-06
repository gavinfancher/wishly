from fastapi.testclient import TestClient

from tests.conftest import as_user

MOM = {"title": "Mom's birthday", "month": 10, "day": 12, "days_before": [0, 7, 7, 1]}


def test_first_request_creates_the_user(client: TestClient) -> None:
    me = client.get("/v1/me").json()

    assert me["id"] == "user_a"
    assert me["email"] == "user_a@example.com"
    assert me["onboarded_at"] is None


def test_update_me_keeps_fields_not_sent(client: TestClient) -> None:
    client.patch("/v1/me", json={"timezone": "America/Chicago"})
    me = client.patch("/v1/me", json={"send_hour": 9, "onboarded": True}).json()

    assert me["timezone"] == "America/Chicago"
    assert me["send_hour"] == 9
    assert me["onboarded_at"] is not None


def test_update_me_rejects_unknown_timezone(client: TestClient) -> None:
    assert client.patch("/v1/me", json={"timezone": "Mars/Olympus"}).status_code == 422


def test_reminder_crud(client: TestClient) -> None:
    created = client.post("/v1/reminders", json=MOM)
    assert created.status_code == 201
    reminder = created.json()
    assert reminder["days_before"] == [7, 1, 0]  # deduplicated, furthest first

    assert client.get("/v1/reminders").json() == [reminder]

    updated = client.put(f"/v1/reminders/{reminder['id']}", json=MOM | {"days_before": [3]})
    assert updated.json()["days_before"] == [3]

    assert client.delete(f"/v1/reminders/{reminder['id']}").status_code == 204
    assert client.get("/v1/reminders").json() == []


def test_impossible_date_is_rejected(client: TestClient) -> None:
    assert client.post("/v1/reminders", json=MOM | {"month": 4, "day": 31}).status_code == 422


def test_users_cannot_touch_each_others_reminders(client: TestClient) -> None:
    reminder_id = client.post("/v1/reminders", json=MOM).json()["id"]
    url = f"/v1/reminders/{reminder_id}"
    user_b = as_user("user_b")

    assert client.get("/v1/reminders", headers=user_b).json() == []
    assert client.put(url, json=MOM, headers=user_b).status_code == 404
    assert client.delete(url, headers=user_b).status_code == 404
    assert len(client.get("/v1/reminders").json()) == 1  # still there for user_a
