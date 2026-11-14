from collections.abc import Iterable

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from support_agent.api import create_app
from support_agent.api.ratelimit import RateLimiter
from support_agent.config import Settings
from support_agent.llm import ModelResponse
from tests.conftest import ServiceFactory, answer, call

ADMIN = ("admin", "correct-horse-battery-staple")


@pytest.fixture
def make_client(make_service: ServiceFactory):  # type: ignore[no-untyped-def]
    def factory(responses: Iterable[ModelResponse] = (), **settings: object) -> TestClient:
        service, _ = make_service(responses)
        config = Settings(
            _env_file=None,
            admin_password=SecretStr(ADMIN[1]),
            **settings,  # type: ignore[arg-type]
        )
        return TestClient(create_app(config, service))

    return factory


def test_chat_round_trip(make_client) -> None:  # type: ignore[no-untyped-def]
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


def test_chat_continues_a_conversation(make_client) -> None:  # type: ignore[no-untyped-def]
    with make_client([answer("Hi!"), answer("Glad to help.")]) as client:
        first = client.post("/api/chat", json={"message": "hello"}).json()
        second = client.post(
            "/api/chat", json={"message": "thanks", "conversation_id": first["conversation_id"]}
        ).json()
    assert second["conversation_id"] == first["conversation_id"]


def test_unknown_conversation_returns_404(make_client) -> None:  # type: ignore[no-untyped-def]
    with make_client() as client:
        response = client.post("/api/chat", json={"message": "hi", "conversation_id": "nope"})
    assert response.status_code == 404


@pytest.mark.parametrize(("message", "status"), [("   ", 422), ("x" * 2001, 413), ("", 422)])
def test_chat_rejects_bad_messages(make_client, message: str, status: int) -> None:  # type: ignore[no-untyped-def]
    with make_client() as client:
        assert client.post("/api/chat", json={"message": message}).status_code == status


def test_chat_is_rate_limited(make_client) -> None:  # type: ignore[no-untyped-def]
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


def test_widget_and_demo_page_are_served(make_client) -> None:  # type: ignore[no-untyped-def]
    with make_client() as client:
        widget = client.get("/widget.js")
        page = client.get("/")
    assert widget.status_code == 200
    assert "javascript" in widget.headers["content-type"]
    assert ".innerHTML" not in widget.text
    assert "insertAdjacentHTML" not in widget.text
    assert '<script src="/widget.js"' in page.text


def test_admin_requires_password(make_client) -> None:  # type: ignore[no-untyped-def]
    with make_client() as client:
        assert client.get("/admin").status_code == 401
        assert client.get("/admin", auth=("admin", "wrong")).status_code == 401
        assert client.get("/admin", auth=ADMIN).status_code == 200


def test_admin_is_disabled_without_password(make_service: ServiceFactory) -> None:
    service, _ = make_service([])
    config = Settings(_env_file=None)
    with TestClient(create_app(config, service)) as client:
        assert client.get("/admin", auth=ADMIN).status_code == 404


def test_admin_shows_handoffs_and_resolves_them(make_client) -> None:  # type: ignore[no-untyped-def]
    responses = [
        call("hand_off_to_human", category="refund", summary="Refund for TS-1001."),
        answer("A person will follow up."),
    ]
    with make_client(responses) as client:
        chat = client.post("/api/chat", json={"message": "refund please"}).json()
        assert chat["handed_off"] is True

        dashboard = client.get("/admin", auth=ADMIN)
        assert "Refund for TS-1001." in dashboard.text

        conversation = client.get(f"/admin/conversations/{chat['conversation_id']}", auth=ADMIN)
        assert "refund please" in conversation.text

        cross_site = client.post(
            "/admin/handoffs/1/resolve", auth=ADMIN, headers={"Origin": "https://evil.example"}
        )
        assert cross_site.status_code == 403

        resolved = client.post(
            "/admin/handoffs/1/resolve",
            auth=ADMIN,
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert resolved.status_code == 303
        assert "Nothing waiting" in client.get("/admin", auth=ADMIN).text


def test_admin_escapes_customer_text(make_client) -> None:  # type: ignore[no-untyped-def]
    with make_client([answer("ok")]) as client:
        chat = client.post("/api/chat", json={"message": "<script>alert(1)</script>"}).json()
        page = client.get(f"/admin/conversations/{chat['conversation_id']}", auth=ADMIN)
    assert "<script>alert(1)</script>" not in page.text
    assert "&lt;script&gt;" in page.text
