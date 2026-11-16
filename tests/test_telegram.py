import json
import threading
from typing import Any

import httpx
import pytest

from support_agent.channels.telegram import (
    HANDOFF_NOTICE,
    NEW_CONVERSATION_REPLY,
    NON_TEXT_REPLY,
    RATE_LIMIT_REPLY,
    TelegramBot,
    TelegramClient,
    TelegramError,
    split_message,
    to_telegram_html,
)
from tests.conftest import ServiceFactory, answer, call

TOKEN = "123:test-token"


class FakeTelegram:
    """Records Bot API calls and serves queued getUpdates batches."""

    def __init__(self, updates: list[list[dict[str, Any]]] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._updates = list(updates or [])

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path.startswith(f"/bot{TOKEN}/")
        method = request.url.path.rsplit("/", 1)[1]
        payload = json.loads(request.content)
        self.calls.append((method, payload))
        if method == "getUpdates":
            batch = self._updates.pop(0) if self._updates else []
            return httpx.Response(200, json={"ok": True, "result": batch})
        return httpx.Response(200, json={"ok": True, "result": True})

    def client(self) -> TelegramClient:
        return TelegramClient(TOKEN, transport=httpx.MockTransport(self.handler))

    def sent_texts(self) -> list[str]:
        return [p["text"] for m, p in self.calls if m == "sendMessage"]


def message(text: str | None, chat_id: int = 42, chat_type: str = "private") -> dict[str, Any]:
    msg: dict[str, Any] = {"chat": {"id": chat_id, "type": chat_type}}
    if text is not None:
        msg["text"] = text
    return {"update_id": 1, "message": msg}


def make_bot(
    make_service: ServiceFactory, responses: list[Any], fake: FakeTelegram, **kwargs: Any
) -> TelegramBot:
    service, _ = make_service(responses)
    return TelegramBot(fake.client(), service, greeting="Hi there!", **kwargs)


# --- Formatting ---------------------------------------------------------------


def test_html_is_escaped_and_bold_is_converted() -> None:
    assert to_telegram_html("Tracking **9400** <b>x</b> & more") == (
        "Tracking <b>9400</b> &lt;b&gt;x&lt;/b&gt; &amp; more"
    )


def test_long_messages_are_split_on_line_breaks() -> None:
    text = "\n".join(["line " * 20] * 10)
    chunks = split_message(text, limit=250)
    assert all(len(c) <= 250 for c in chunks)
    assert "".join(c.replace("\n", "") for c in chunks).replace(" ", "") == text.replace(
        "\n", ""
    ).replace(" ", "")


def test_a_single_long_word_is_hard_split() -> None:
    assert split_message("x" * 10, limit=4) == ["xxxx", "xxxx", "xx"]


# --- Bot behaviour -----------------------------------------------------------


def test_start_sends_the_greeting(make_service: ServiceFactory) -> None:
    fake = FakeTelegram()
    make_bot(make_service, [], fake).handle_update(message("/start"))
    assert fake.sent_texts() == ["Hi there!"]


def test_questions_are_answered_through_the_agent(make_service: ServiceFactory) -> None:
    fake = FakeTelegram()
    bot = make_bot(make_service, [answer("Your order shipped. Tracking **9400**.")], fake)

    bot.handle_update(message("Where is my order?"))

    assert fake.sent_texts() == ["Your order shipped. Tracking <b>9400</b>."]
    assert ("sendChatAction", {"chat_id": 42, "action": "typing"}) in fake.calls
    assert all(p.get("parse_mode") == "HTML" for m, p in fake.calls if m == "sendMessage")


def test_new_command_starts_a_fresh_conversation(make_service: ServiceFactory) -> None:
    fake = FakeTelegram()
    service, model = make_service([answer("Hi!"), answer("Fresh.")])
    bot = TelegramBot(fake.client(), service, greeting="Hi there!")

    bot.handle_update(message("hello"))
    bot.handle_update(message("/new"))
    bot.handle_update(message("new question"))

    assert NEW_CONVERSATION_REPLY in fake.sent_texts()
    messages, _ = model.requests[1]
    assert [m.content for m in messages[1:]] == ["new question"]


def test_handoff_sends_a_notice_once(make_service: ServiceFactory) -> None:
    fake = FakeTelegram()
    bot = make_bot(
        make_service,
        [
            call("hand_off_to_human", category="refund", summary="Refund."),
            answer("A person will follow up."),
            answer("You're welcome."),
        ],
        fake,
    )

    bot.handle_update(message("refund please"))
    bot.handle_update(message("thanks"))

    assert fake.sent_texts().count(HANDOFF_NOTICE) == 1


def test_non_text_messages_get_a_polite_reply(make_service: ServiceFactory) -> None:
    fake = FakeTelegram()
    make_bot(make_service, [], fake).handle_update(message(None))
    assert fake.sent_texts() == [NON_TEXT_REPLY]


def test_group_chats_are_ignored(make_service: ServiceFactory) -> None:
    fake = FakeTelegram()
    make_bot(make_service, [], fake).handle_update(message("hi", chat_type="group"))
    assert fake.calls == []


def test_each_chat_is_rate_limited(make_service: ServiceFactory) -> None:
    fake = FakeTelegram()
    bot = make_bot(make_service, [answer("ok")], fake, rate_limit_per_minute=1)

    bot.handle_update(message("one"))
    bot.handle_update(message("two"))

    assert fake.sent_texts() == ["ok", RATE_LIMIT_REPLY]


def test_polling_tracks_the_offset_and_stops(make_service: ServiceFactory) -> None:
    stop = threading.Event()
    updates = [
        [{**message("/start"), "update_id": 7}],
        [],
    ]
    fake = FakeTelegram(updates)
    bot = make_bot(make_service, [], fake)
    original = fake.handler

    def stop_after_second_poll(request: httpx.Request) -> httpx.Response:
        response = original(request)
        if sum(1 for m, _ in fake.calls if m == "getUpdates") >= 2:
            stop.set()
        return response

    bot._client = TelegramClient(TOKEN, transport=httpx.MockTransport(stop_after_second_poll))
    bot.run_polling(stop, poll_timeout=0)

    polls = [p for m, p in fake.calls if m == "getUpdates"]
    assert "offset" not in polls[0]
    assert polls[1]["offset"] == 8
    assert fake.sent_texts() == ["Hi there!"]


def test_api_errors_do_not_leak_the_token() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect to {request.url}")

    client = TelegramClient(TOKEN, transport=httpx.MockTransport(fail))
    with pytest.raises(TelegramError) as error:
        client.send_message(1, "hi")
    assert TOKEN not in str(error.value)
