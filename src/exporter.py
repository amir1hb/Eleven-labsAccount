"""CSV and TXT export of accounts."""
from __future__ import annotations

import csv
import io
from typing import Iterable

from .supabase_client import Account


CSV_COLUMNS = [
    "email",
    "elevenlabs_password",
    "mailbox_password",
    "domain",
    "status",
    "created_at",
    "verified_at",
]


def to_csv(accounts: Iterable[Account]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for account in accounts:
        writer.writerow(
            {
                "email": account.email,
                "elevenlabs_password": account.elevenlabs_password,
                "mailbox_password": account.mailbox_password,
                "domain": account.domain,
                "status": account.status,
                "created_at": str(account.created_at),
                "verified_at": str(account.verified_at) if account.verified_at else "",
            }
        )
    return buffer.getvalue().encode("utf-8")


def to_txt(accounts: Iterable[Account]) -> bytes:
    """`email:elevenlabs_password` per line, paste-ready."""
    lines = [f"{a.email}:{a.elevenlabs_password}" for a in accounts]
    return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""
