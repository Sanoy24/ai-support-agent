from collections.abc import Callable, Iterable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from support_agent.api import create_app
from support_agent.api.auth import SessionSigner
from support_agent.api.ratelimit import RateLimiter
from support_agent.config import Settings
from support_agent.llm import ModelResponse
from tests.conftest import ServiceFactory, answer, call

PASSWORD = "correct-horse-battery-staple"

ClientFactory = Callable[..., TestClient]


@pytest.fixture
def frontend(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('app')")
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "widget.js").write_text("/* widget */")
    return tmp_path


@pytest.fixture
def make_client(make_service: ServiceFactory, frontend: Path) -> ClientFactory:
    def factory(
        responses: Iterable[ModelResponse] = (), *, admin: bool = True, **overrides: object
    ) -> TestClient:
        service, _ = make_service(responses)
        values: dict[str, object] = {"admin_password": SecretStr(PASSWORD)} if admin else {}
        values.update(overrides)
        config = Settings.model_validate(values)
        return TestClient(create_app(config, service, frontend_dir=frontend))

    return factory


def login(client: TestClient) -> None:
    assert client.post("/api/admin/login", json={"password": PASSWORD}).status_code == 204


# --- Chat -------------------------------------------------------------------


def test_chat_round_trip(make_client: ClientFactory) -> None:
    with make_client(
        [call("search_help_center", query="return window"), answer("You have 30 days.")]
    ) as client:
        response = client.post("/api/chat", json={"message": "How long to return?"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "You have 30 days."
    assert body["handed_off"] is False
    assert body["conversation_id"]
    assert any(s["source"] == "returns.md" for s in body["sources"])


def test_chat_continues_a_conversation(make_client: ClientFactory) -> None:
    with make_client([answer("Hi!"), answer("Glad to help.")]) as client:
        first = client.post("/api/chat", json={"message": "hello"}).json()
        second = client.post(
            "/api/chat", json={"message": "thanks", "conversation_id": first["conversation_id"]}
        ).json()
    assert second["conversation_id"] == first["conversation_id"]


def test_unknown_conversation_returns_404(make_client: ClientFactory) -> None:
    with make_client() as client:
        response = client.post("/api/chat", json={"message": "hi", "conversation_id": "nope"})
    assert response.status_code == 404


@pytest.mark.parametrize(("message", "status"), [("   ", 422), ("x" * 2001, 413), ("", 422)])
def test_chat_rejects_bad_messages(make_client: ClientFactory, message: str, status: int) -> None:
    with make_client() as client:
        assert client.post("/api/chat", json={"message": message}).status_code == status


def test_chat_is_rate_limited(make_client: ClientFactory) -> None:
    with make_client([answer("ok"), answer("ok")], chat_rate_limit_per_minute=2) as client:
        codes = [client.post("/api/chat", json={"message": "hi"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_rate_limiter_window_slides() -> None:
    now = [0.0]
    limiter = RateLimiter(2, window_seconds=60, clock=lambda: now[0])
    assert [limiter.allow("ip"), limiter.allow("ip"), limiter.allow("ip")] == [True, True, False]
    assert limiter.allow("other-ip") is True
    now[0] = 61.0
    assert limiter.allow("ip") is True


def test_store_endpoint_lists_catalog(make_client: ClientFactory) -> None:
    with make_client() as client:
        body = client.get("/api/store").json()
    assert body["name"] == "Trailhead Supply Co."
    assert any(p["sku"] == "TS-TENT-2P" for p in body["products"])


# --- Frontend ---------------------------------------------------------------


def test_frontend_routes_fall_back_to_index(make_client: ClientFactory) -> None:
    with make_client() as client:
        assert client.get("/").text == "<div id=root></div>"
        assert client.get("/admin/conversations/abc").text == "<div id=root></div>"
        assert client.get("/assets/app.js").status_code == 200
        widget = client.get("/widget.js")
        assert widget.status_code == 200
        assert "javascript" in widget.headers["content-type"]
        assert widget.headers["cache-control"] == "no-cache"


def test_unknown_api_routes_are_not_swallowed_by_the_frontend(make_client: ClientFactory) -> None:
    with make_client() as client:
        assert client.get("/api/nope").status_code == 404


def test_frontend_does_not_serve_files_outside_its_folder(make_client: ClientFactory) -> None:
    with make_client() as client:
        response = client.get("/..%2F..%2Fpyproject.toml")
    assert "[project]" not in response.text


# --- Admin ------------------------------------------------------------------


def test_admin_api_requires_login(make_client: ClientFactory) -> None:
    with make_client() as client:
        assert client.get("/api/admin/overview").status_code == 401
        assert client.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
        login(client)
        assert client.get("/api/admin/session").status_code == 204
        assert client.get("/api/admin/overview").json()["total_conversations"] == 0
        client.post("/api/admin/logout")
        assert client.get("/api/admin/overview").status_code == 401


def test_session_cookie_is_httponly_and_strict(make_client: ClientFactory) -> None:
    with make_client() as client:
        response = client.post("/api/admin/login", json={"password": PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/api/admin" in cookie


def test_forged_or_expired_sessions_are_rejected() -> None:
    now = [1000.0]
    signer = SessionSigner(b"secret", clock=lambda: now[0])
    token = signer.issue()
    assert signer.verify(token)
    assert not signer.verify(token[:-1] + ("0" if token[-1] != "0" else "1"))
    assert not SessionSigner(b"other-secret", clock=lambda: now[0]).verify(token)
    assert not signer.verify("garbage")
    now[0] += 13 * 60 * 60
    assert not signer.verify(token)


def test_login_is_rate_limited(make_client: ClientFactory) -> None:
    with make_client() as client:
        codes = [
            client.post("/api/admin/login", json={"password": "wrong"}).status_code
            for _ in range(6)
        ]
    assert codes[-1] == 429


def test_admin_is_disabled_without_password(make_client: ClientFactory) -> None:
    with make_client(admin=False) as client:
        assert client.post("/api/admin/login", json={"password": PASSWORD}).status_code == 404
        assert client.get("/api/admin/overview").status_code == 404


def test_admin_handoff_flow(make_client: ClientFactory) -> None:
    responses = [
        call("hand_off_to_human", category="refund", summary="Refund for TS-1001."),
        answer("A person will follow up."),
        call("search_help_center", query="kayak"),
        answer("I don't know."),
    ]
    with make_client(responses) as client:
        chat = client.post("/api/chat", json={"message": "refund please"}).json()
        client.post("/api/chat", json={"message": "kayaks?"})
        login(client)

        overview = client.get("/api/admin/overview").json()
        assert overview["total_conversations"] == 2
        assert overview["open_handoffs"] == 1
        assert overview["unanswered_questions"] == 1
        assert overview["handed_off_rate"] == 0.5

        [handoff] = client.get("/api/admin/handoffs").json()
        assert handoff["summary"] == "Refund for TS-1001."

        [question] = client.get("/api/admin/unanswered").json()
        assert question["question"] == "kayaks?"

        conversations = client.get("/api/admin/conversations").json()
        assert {c["preview"] for c in conversations} == {"refund please", "kayaks?"}

        detail = client.get(f"/api/admin/conversations/{chat['conversation_id']}").json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][1]["tools"] == ["hand_off_to_human"]

        resolved = client.post(f"/api/admin/handoffs/{handoff['id']}/resolve").json()
        assert resolved["resolved"] is True
        assert client.get("/api/admin/handoffs").json() == []
        assert client.get("/api/admin/overview").json()["open_handoffs"] == 0


def test_admin_detail_404s(make_client: ClientFactory) -> None:
    with make_client() as client:
        login(client)
        assert client.get("/api/admin/conversations/missing").status_code == 404
        assert client.post("/api/admin/handoffs/999/resolve").status_code == 404
