"""Telegram channel: the same support agent, reachable as a Telegram bot.

Uses long polling (``getUpdates``), so it works on a laptop or a server with
no public URL. Create a bot with @BotFather and set ``TELEGRAM_BOT_TOKEN``.
"""

from __future__ import annotations

import html
import logging
import re
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from support_agent.api.ratelimit import RateLimiter
from support_agent.db import Channel
from support_agent.service import SupportService

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)

NEW_CONVERSATION_REPLY = "Started a new conversation. What can I help you with?"
NON_TEXT_REPLY = "Sorry, I can only read text messages for now. Please type your question."
RATE_LIMIT_REPLY = "You're sending messages very quickly. Please wait a moment and try again."
ERROR_REPLY = "Sorry, something went wrong on our side. Please try again in a minute."
HANDOFF_NOTICE = "A member of our team will follow up on this chat."


class TelegramError(RuntimeError):
    """Raised when the Telegram Bot API returns an error."""


def to_telegram_html(text: str) -> str:
    """Escape text for Telegram's HTML mode and turn **bold** into <b>bold</b>."""
    return _BOLD.sub(r"<b>\1</b>", html.escape(text, quote=False))


def split_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split long replies on paragraph or line breaks to fit Telegram's limit."""
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


class TelegramClient:
    """Minimal client for the Telegram Bot API."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.telegram.org",
        timeout: float = 40.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=f"{base_url}/bot{token}", timeout=timeout, transport=transport
        )

    def close(self) -> None:
        self._client.close()

    def _call(self, method: str, payload: dict[str, Any]) -> Any:
        try:
            response = self._client.post(f"/{method}", json=payload)
        except httpx.HTTPError as exc:
            # The exception text can include the URL, which contains the token.
            raise TelegramError(f"Could not reach Telegram ({type(exc).__name__})") from None
        try:
            body = response.json()
        except ValueError:
            raise TelegramError(f"Telegram returned HTTP {response.status_code}") from None
        if not body.get("ok"):
            raise TelegramError(f"Telegram error: {body.get('description', 'unknown')}")
        return body.get("result")

    def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        result: list[dict[str, Any]] = self._call("getUpdates", payload)
        return result

    def send_message(self, chat_id: int | str, text: str) -> None:
        for chunk in split_message(text):
            self._call(
                "sendMessage",
                {"chat_id": chat_id, "text": to_telegram_html(chunk), "parse_mode": "HTML"},
            )

    def send_typing(self, chat_id: int | str) -> None:
        self._call("sendChatAction", {"chat_id": chat_id, "action": "typing"})


class TelegramBot:
    """Routes Telegram messages to the support service and sends the replies."""

    def __init__(
        self,
        client: TelegramClient,
        service: SupportService,
        *,
        greeting: str,
        rate_limit_per_minute: int = 20,
        workers: int = 4,
        typing_interval: float = 4.0,
    ) -> None:
        self._client = client
        self._service = service
        self._greeting = greeting
        self._limiter = RateLimiter(rate_limit_per_minute)
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="telegram")
        self._chat_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
        self._typing_interval = typing_interval

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") != "private" or "id" not in chat:
            return  # Only one-to-one chats; groups and channels are ignored.
        chat_id = chat["id"]
        chat_ref = str(chat_id)
        text = (message.get("text") or "").strip()

        # Messages from one chat are handled in order, one at a time.
        with self._chat_locks[chat_ref]:
            try:
                self._respond(chat_id, chat_ref, text)
            except Exception:
                logger.exception("Failed to handle a Telegram message")
                self._safe_send(chat_id, ERROR_REPLY)

    def _respond(self, chat_id: int, chat_ref: str, text: str) -> None:
        if not text:
            self._client.send_message(chat_id, NON_TEXT_REPLY)
            return
        command = text.split(maxsplit=1)[0].split("@")[0].lower() if text.startswith("/") else ""
        if command in {"/start", "/help"}:
            self._client.send_message(chat_id, self._greeting)
            return
        if command == "/new":
            self._service.close_channel_conversation(Channel.TELEGRAM, chat_ref)
            self._client.send_message(chat_id, NEW_CONVERSATION_REPLY)
            return
        if not self._limiter.allow(chat_ref):
            self._client.send_message(chat_id, RATE_LIMIT_REPLY)
            return

        with self._typing(chat_id):
            result = self._service.handle_channel_message(Channel.TELEGRAM, chat_ref, text)
        self._client.send_message(chat_id, result.reply)
        if result.newly_handed_off:
            self._client.send_message(chat_id, HANDOFF_NOTICE)

    def _typing(self, chat_id: int) -> _TypingIndicator:
        return _TypingIndicator(self._client, chat_id, self._typing_interval)

    def _safe_send(self, chat_id: int, text: str) -> None:
        try:
            self._client.send_message(chat_id, text)
        except TelegramError:
            logger.warning("Could not send an error reply on Telegram")

    def run_polling(self, stop: threading.Event, poll_timeout: int = 25) -> None:
        """Fetch updates until ``stop`` is set, handling each in a worker thread."""
        offset: int | None = None
        backoff = 1.0
        logger.info("Telegram bot started (long polling)")
        while not stop.is_set():
            try:
                updates = self._client.get_updates(offset, timeout=poll_timeout)
                backoff = 1.0
            except TelegramError as exc:
                logger.warning("Telegram polling failed: %s. Retrying in %.0fs", exc, backoff)
                stop.wait(backoff)
                backoff = min(backoff * 2, 30.0)
                continue
            for update in updates:
                offset = int(update["update_id"]) + 1
                self._executor.submit(self.handle_update, update)
        self._executor.shutdown(wait=True)
        logger.info("Telegram bot stopped")


class _TypingIndicator:
    """Keeps Telegram's "typing…" status visible while the agent works."""

    def __init__(self, client: TelegramClient, chat_id: int, interval: float) -> None:
        self._client = client
        self._chat_id = chat_id
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> _TypingIndicator:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._client.send_typing(self._chat_id)
            except TelegramError:
                return
            self._stop.wait(self._interval)
