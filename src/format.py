"""Telegram MarkdownV2 formatting helpers.

MarkdownV2 has many reserved characters that must be escaped outside of
code blocks. These helpers centralise the escaping logic so credentials
render as tap-to-copy `<code>` blocks without breaking the message send.
"""
from __future__ import annotations

from datetime import datetime, timezone

# All MarkdownV2 reserved characters per Telegram docs.
_RESERVED = r"_*[]()~`>#+-=|{}.!\\"


def escape_md(text: str) -> str:
    """Escape every MarkdownV2 reserved char so plain text renders verbatim."""
    out = []
    for ch in text:
        if ch in _RESERVED:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def code(value: str) -> str:
    """Wrap a value in inline `<code>` (tap-to-copy in Telegram).

    Inside inline code, only backticks and backslashes need escaping.
    """
    safe = value.replace("\\", "\\\\").replace("`", "\\`")
    return f"`{safe}`"


def render_account_success(
    *,
    email: str,
    mailbox_password: str,
    elevenlabs_password: str,
    pinmx_login_url: str,
) -> str:
    """Render the final success message for a created account.

    Format (MarkdownV2):

        ✅ Account ready

        📬 Mailbox login
        https://mail-client.pinmx.com
        Email: `kx9mp@pinmx.net`
        Pass: `Pq7$Rt2vNkLm@9Yz`

        🎙 ElevenLabs
        Email: `kx9mp@pinmx.net`
        Pass: `Xm9!2vRq8KpL$nW3`
    """
    parts = [
        "✅ Account ready",
        "",
        "📬 Mailbox login",
        escape_md(pinmx_login_url),
        f"Email: {code(email)}",
        f"Pass: {code(mailbox_password)}",
        "",
        "🎙 ElevenLabs",
        f"Email: {code(email)}",
        f"Pass: {code(elevenlabs_password)}",
    ]
    return "\n".join(parts)


def render_progress(step: int, total: int, label: str) -> str:
    """Single-line progress message used during account creation."""
    return escape_md(f"[{step}/{total}] {label}")


def render_failure(step: int, total: int, message: str) -> str:
    return escape_md(f"❌ Failed at step [{step}/{total}]: {message}")


def render_bulk_progress(rows: list[str], total: int, done: int, ok: int, fail: int) -> str:
    """Render the running bulk progress message body."""
    header = escape_md(f"Creating {total} accounts…") if done < total else escape_md(
        f"Done. {ok} ok, {fail} failed."
    )
    body = "\n".join(escape_md(r) for r in rows)
    return f"{header}\n\n{body}" if rows else header


def humanise_when(ts: datetime | str) -> str:
    """Render a created_at timestamp as a friendly relative label."""
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts  # fall back to raw string
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - ts
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86_400:
        return f"{seconds // 3600}h ago"
    days = seconds // 86_400
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    return ts.date().isoformat()
