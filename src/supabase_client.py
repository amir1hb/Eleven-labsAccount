"""Supabase wrapper for the bot's two tables: accounts, allowed_users.

We use the official supabase-py client with the service-role key so RLS
doesn't get in the way. All callers go through the typed helpers below.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from supabase import Client, create_client


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- dataclasses ------------------------------------------------------------


@dataclass
class Account:
    id: str
    email: str
    mailbox_password: str
    elevenlabs_password: str
    domain: str
    status: str
    error: str | None
    created_by: int
    created_at: str | datetime
    verified_at: str | datetime | None = None
    failed_at: str | datetime | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Account":
        return cls(
            id=row["id"],
            email=row["email"],
            mailbox_password=row["mailbox_password"],
            elevenlabs_password=row["elevenlabs_password"],
            domain=row["domain"],
            status=row["status"],
            error=row.get("error"),
            created_by=row["created_by"],
            created_at=row["created_at"],
            verified_at=row.get("verified_at"),
            failed_at=row.get("failed_at"),
        )


@dataclass
class AllowedUser:
    telegram_user_id: int
    role: str
    added_by: int | None
    added_at: str | datetime


# ---- repository -------------------------------------------------------------


class Repo:
    def __init__(self, url: str, service_key: str):
        self._client: Client = create_client(url, service_key)

    # accounts -----------------------------------------------------------------

    def insert_pending_account(
        self,
        *,
        email: str,
        mailbox_password: str,
        elevenlabs_password: str,
        domain: str,
        created_by: int,
    ) -> Account:
        row = (
            self._client.table("accounts")
            .insert(
                {
                    "email": email,
                    "mailbox_password": mailbox_password,
                    "elevenlabs_password": elevenlabs_password,
                    "domain": domain,
                    "status": "pending",
                    "created_by": created_by,
                }
            )
            .execute()
        )
        return Account.from_row(row.data[0])

    def mark_active(self, account_id: str) -> None:
        self._client.table("accounts").update(
            {"status": "active", "verified_at": _utc_now_iso(), "error": None}
        ).eq("id", account_id).execute()

    def mark_failed(self, account_id: str, error: str) -> None:
        self._client.table("accounts").update(
            {"status": "failed", "error": error[:500], "failed_at": _utc_now_iso()}
        ).eq("id", account_id).execute()

    def get_account(self, account_id: str) -> Account | None:
        row = (
            self._client.table("accounts")
            .select("*")
            .eq("id", account_id)
            .single()
            .execute()
        )
        return Account.from_row(row.data) if row.data else None

    def list_accounts(
        self,
        *,
        created_by: int | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Account], int]:
        query = self._client.table("accounts").select("*", count="exact")
        if created_by is not None:
            query = query.eq("created_by", created_by)
        # Reverse-chronological.
        query = query.order("created_at", desc=True)
        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)
        result = query.execute()
        accounts = [Account.from_row(r) for r in (result.data or [])]
        total = int(result.count or 0)
        return accounts, total

    def all_accounts(self, *, created_by: int | None) -> list[Account]:
        query = self._client.table("accounts").select("*")
        if created_by is not None:
            query = query.eq("created_by", created_by)
        query = query.order("created_at", desc=True)
        result = query.execute()
        return [Account.from_row(r) for r in (result.data or [])]

    def stats(self, *, created_by: int | None) -> dict[str, int]:
        """Return a small dict of counts — total / today / active / failed."""
        # Pull a slim projection; bot users won't have huge tables.
        query = self._client.table("accounts").select("status,created_at")
        if created_by is not None:
            query = query.eq("created_by", created_by)
        result = query.execute()
        rows = result.data or []
        today_str = datetime.now(timezone.utc).date().isoformat()
        total = len(rows)
        total_active = sum(1 for r in rows if r["status"] == "active")
        total_failed = sum(1 for r in rows if r["status"] == "failed")
        today_rows = [r for r in rows if str(r["created_at"]).startswith(today_str)]
        today_total = len(today_rows)
        today_active = sum(1 for r in today_rows if r["status"] == "active")
        today_failed = sum(1 for r in today_rows if r["status"] == "failed")
        return {
            "total": total,
            "total_active": total_active,
            "total_failed": total_failed,
            "today_total": today_total,
            "today_active": today_active,
            "today_failed": today_failed,
        }

    # allowed_users ------------------------------------------------------------

    def upsert_allowed(
        self, telegram_user_id: int, role: str = "user", added_by: int | None = None
    ) -> None:
        self._client.table("allowed_users").upsert(
            {
                "telegram_user_id": telegram_user_id,
                "role": role,
                "added_by": added_by,
            }
        ).execute()

    def remove_allowed(self, telegram_user_id: int) -> bool:
        result = (
            self._client.table("allowed_users")
            .delete()
            .eq("telegram_user_id", telegram_user_id)
            .execute()
        )
        return bool(result.data)

    def get_allowed(self, telegram_user_id: int) -> AllowedUser | None:
        result = (
            self._client.table("allowed_users")
            .select("*")
            .eq("telegram_user_id", telegram_user_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        row = rows[0]
        return AllowedUser(
            telegram_user_id=row["telegram_user_id"],
            role=row["role"],
            added_by=row.get("added_by"),
            added_at=row["added_at"],
        )

    def list_allowed(self) -> list[AllowedUser]:
        result = (
            self._client.table("allowed_users")
            .select("*")
            .order("added_at", desc=False)
            .execute()
        )
        return [
            AllowedUser(
                telegram_user_id=r["telegram_user_id"],
                role=r["role"],
                added_by=r.get("added_by"),
                added_at=r["added_at"],
            )
            for r in (result.data or [])
        ]

    def bootstrap_admin(self, telegram_user_id: int) -> None:
        """Ensure the admin row exists with role='admin'."""
        existing = self.get_allowed(telegram_user_id)
        if existing and existing.role == "admin":
            return
        self.upsert_allowed(telegram_user_id, role="admin", added_by=telegram_user_id)
        logger.info("Bootstrap admin {} upserted with role=admin", telegram_user_id)
