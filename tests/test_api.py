"""HTTP contract of the backend the Flutter client talks to."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import visionleader
from visionleader.api import dependencies
from visionleader.api.app import app
from visionleader.api.routers import image as image_router
from visionleader.api.routers import plan as plan_router
from visionleader.api.services import image_analysis

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, agent, fake_planner, converter) -> TestClient:
    monkeypatch.setattr(dependencies, "_conversation_agent", agent)
    monkeypatch.setattr(plan_router, "planner", fake_planner)
    monkeypatch.setattr(plan_router, "hierarchical_converter", converter)
    return TestClient(app)


def test_root_lists_the_endpoints(client: TestClient) -> None:
    body = client.get("/").json()
    assert body["version"] == visionleader.__version__
    assert body["endpoints"]["conversation"] == "POST /api/conversation"


def test_openapi_schema_is_served(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert {"/api/plan", "/api/conversation", "/api/analyze-image"} <= set(schema["paths"])


def test_domain_endpoint_returns_the_pddl_domain(client: TestClient) -> None:
    domain = client.get("/api/domain").json()["domain"]
    assert "(define (domain campus-navigation)" in domain


def test_plan_endpoint(client: TestClient, fake_planner) -> None:
    response = client.post(
        "/api/plan",
        json={
            "initial_state": {"building": 1, "floor": 0, "room": "entrance_2"},
            "goal_state": {"building": 1, "floor": 1, "room": "classroom_g_1_4"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert (body["cost"], body["steps"]) == (33, 6)
    assert "(at user classroom_g_1_4)" in fake_planner.problems[0]


@pytest.mark.parametrize(
    "payload",
    [
        {"initial_state": {"floor": 0, "room": "entrance_2"}, "goal_functional": "gym"},
        {"initial_state": {"building": 1, "floor": 0, "room": "entrance_2"}},
        {"initial_state": {"building": 1, "floor": 0}, "goal_functional": "gym"},
    ],
)
def test_plan_endpoint_rejects_incomplete_requests(client: TestClient, payload: dict) -> None:
    assert client.post("/api/plan", json=payload).status_code == 400


def test_conversation_endpoint_runs_a_turn(client: TestClient) -> None:
    first = client.post("/api/conversation", json={"session_id": "api", "user_message": ""})
    assert first.status_code == 200
    assert first.json()["next_input"] == "voice_or_photo"

    second = client.post(
        "/api/conversation",
        json={"session_id": "api", "user_message": "I am at entrance 2 of building G"},
    ).json()
    assert second["context"]["state"] == "ask_destination"
    assert second["needs_input"] is True


def test_image_endpoint_validates_before_calling_the_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(image_router, "COLAB_API_URL", "")
    files = {"file": ("plate.png", PNG, "image/png")}

    unknown = client.post("/api/analyze-image", files=files, data={"prompt_id": "nope"})
    assert unknown.status_code == 400

    gif = {"file": ("plate.gif", b"GIF89a", "image/gif")}
    assert (
        client.post("/api/analyze-image", files=gif, data={"prompt_id": "room_plate"}).status_code
        == 400
    )

    offline = client.post("/api/analyze-image", files=files, data={"prompt_id": "room_plate"})
    assert offline.status_code == 503


class _ColabReply:
    status_code = 200

    def __init__(self, text: str) -> None:
        self._text = text

    def json(self) -> dict:
        return {"success": True, "response": self._text}


@pytest.mark.parametrize(
    ("model_output", "success", "location_id"),
    [
        ("(at user classroom_g_1_4)", True, "classroom_g_1_4"),
        ("(at user classroom_x_9_9)", False, None),  # hallucinated id is rejected
    ],
)
def test_image_endpoint_grounds_the_model_output(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    model_output: str,
    success: bool,
    location_id: str | None,
) -> None:
    sent = {}

    def fake_post(url, files, data, timeout):
        sent.update(url=url, prompt=data["prompt"])
        return _ColabReply(model_output)

    monkeypatch.setattr(image_router, "COLAB_API_URL", "http://colab.test")
    monkeypatch.setattr(image_analysis.requests, "post", fake_post)

    body = client.post(
        "/api/analyze-image",
        files={"file": ("plate.png", PNG, "image/png")},
        data={"prompt_id": "room_plate"},
    ).json()

    assert sent["url"] == "http://colab.test/analyze"
    assert sent["prompt"].startswith("<image>")
    assert body["success"] is success
    assert body["location_id"] == location_id
    assert body["raw_response"] == model_output


def test_gps_route_degrades_gracefully_without_a_maps_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    body = client.post("/api/gps-route", json={"from_building": 1, "to_building": 2}).json()
    assert body["success"] is False
    assert "GOOGLE_MAPS_API_KEY" in body["error"]


def test_gps_route_rejects_unknown_buildings(client: TestClient) -> None:
    body = client.post("/api/gps-route", json={"from_building": 1, "to_building": 99}).json()
    assert body["success"] is False
    assert "No GPS data" in body["error"]
