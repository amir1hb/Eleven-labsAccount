"""PinMX API client.

Documented endpoints:
- POST {base}/v1/mail/create   — provision a new mailbox.
- POST {base}/v1/mail/list     — list received messages.

Both accept multipart/form-data with a `token` field. Responses are
`{code, msg, data}` — `code: 200` is success.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger


class PinmxError(Exception):
    """Raised when PinMX returns a non-success code."""

    def __init__(self, code: int, msg: str):
        super().__init__(f"PinMX error {code}: {msg}")
        self.code = code
        self.msg = msg


@dataclass
class PinmxMessage:
    raw: dict[str, Any]

    @property
    def from_addr(self) -> str:
        return str(
            self.raw.get("from")
            or self.raw.get("sender")
            or self.raw.get("from_email")
            or ""
        )

    @property
    def to_addr(self) -> str:
        return str(
            self.raw.get("to")
            or self.raw.get("recipient")
            or self.raw.get("to_email")
            or ""
        )

    @property
    def subject(self) -> str:
        return str(self.raw.get("subject") or "")

    @property
    def body(self) -> str:
        # PinMX may return body under various keys depending on version.
        for key in ("html", "body", "content", "text", "html_body"):
            value = self.raw.get(key)
            if isinstance(value, str) and value:
                return value
        return ""


class PinmxClient:
    def __init__(self, *, base_url: str, token: str, timeout: float = 30.0):
        self._base = base_url.rstrip("/")
        self._token = token
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "PinmxClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def _post(self, path: str, fields: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}{path}"
        # Send as multipart/form-data (matches `curl -F`).
        files: dict[str, tuple[None, str]] = {
            "token": (None, self._token),
            **{k: (None, str(v)) for k, v in fields.items() if v is not None},
        }
        response = await self._client.post(url, files=files)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise PinmxError(0, f"non-JSON response: {response.text[:200]}") from exc
        code = int(payload.get("code", 0))
        if code != 200:
            raise PinmxError(code, str(payload.get("msg", "")))
        return payload.get("data") or {}

    async def create_mailbox(
        self,
        *,
        domain: str,
        username: str,
        password: str,
        mark: str | None = None,
    ) -> dict[str, Any]:
        logger.debug("PinMX create_mailbox username={} domain={} mark={}", username, domain, mark)
        return await self._post(
            "/v1/mail/create",
            {
                "domain": domain,
                "username": username,
                "password": password,
                "mark": mark,
            },
        )

    async def list_messages(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        mark: str | None = None,
    ) -> list[PinmxMessage]:
        data = await self._post(
            "/v1/mail/list",
            {"page": page, "limit": limit, "mark": mark},
        )
        # Response shape: {"list": [...], "total": N}
        items = data.get("list") if isinstance(data, dict) else None
        if not items:
            return []
        return [PinmxMessage(raw=item) for item in items if isinstance(item, dict)]

    async def self_check(self) -> None:
        """Verify the token + plan tier by listing messages once."""
        await self._post("/v1/mail/list", {"page": 1, "limit": 1})
