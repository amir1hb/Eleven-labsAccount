"""Temp-Mail API client for creating disposable emails and fetching messages."""
from __future__ import annotations

import asyncio
import httpx
import random
import string
from loguru import logger


class TempMailClient:
    """Client for Temp-Mail API (api.internal.temp-mail.io)."""

    def __init__(self):
        self.base_url = "https://api.internal.temp-mail.io/api/v3"
        self.email = None
        self.token = None

    async def create_mailbox(self) -> dict:
        """Create a new temporary email address."""
        # تولید نام کاربری تصادفی ۱۰ کاراکتری
        name_length = 10
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=name_length))
        
        # دامنه‌های پشتیبانی شده توسط Temp-Mail
        domains = [
            "temp-mail.io",
            "temp-mail.org",
            "temp-mail.com",
            "tmailor.com",
            "kirche.com",
            "dnses.com",
            "tmail.com",
            "tmail.org"
        ]
        domain = random.choice(domains)
        email = f"{username}@{domain}"

        # درخواست به API برای ایجاد ایمیل
        url = f"{self.base_url}/email/new"
        payload = {
            "min_name_length": name_length,
            "max_name_length": name_length
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    self.email = data.get("email")
                    self.token = data.get("token")
                    logger.info(f"✅ Temp-Mail created: {self.email}")
                    return {
                        "email": self.email,
                        "token": self.token
                    }
                else:
                    raise Exception(f"Failed to create mailbox: {response.status_code}")
            except Exception as e:
                raise Exception(f"Failed to create mailbox via Temp-Mail: {str(e)}")

    async def list_messages(self) -> list:
        """Get list of messages for the current mailbox."""
        if not self.token:
            return []

        url = f"{self.base_url}/email/list"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        params = {
            "token": self.token,
            "limit": 20,
            "page": 1
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    messages = data.get("messages", [])
                    # تبدیل به فرمت مورد انتظار در workflow
                    formatted_messages = []
                    for msg in messages:
                        formatted_messages.append({
                            "id": msg.get("id"),
                            "body": msg.get("body_html", "") or msg.get("body_text", ""),
                            "subject": msg.get("subject", ""),
                            "from": msg.get("from", {}).get("email", ""),
                            "to": msg.get("to", {}).get("email", ""),
                            "created_at": msg.get("created_at", "")
                        })
                    return formatted_messages
                else:
                    logger.warning(f"List messages failed: {response.status_code}")
                    return []
            except Exception as e:
                logger.warning(f"List messages error: {e}")
                return []

    async def get_message(self, message_id: str) -> dict:
        """Get full content of a specific message."""
        if not self.token:
            return {}

        url = f"{self.base_url}/email/one"
        params = {
            "token": self.token,
            "id": message_id
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "body": data.get("body_html", "") or data.get("body_text", ""),
                        "subject": data.get("subject", ""),
                        "from": data.get("from", {}).get("email", ""),
                        "to": data.get("to", {}).get("email", ""),
                        "created_at": data.get("created_at", "")
                    }
                else:
                    return {}
            except Exception as e:
                logger.warning(f"Get message error: {e}")
                return {}

    async def delete_mailbox(self) -> bool:
        """Delete the current mailbox (cleanup)."""
        if not self.token:
            return True

        url = f"{self.base_url}/email/delete"
        params = {"token": self.token}

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.delete(url, params=params)
                return response.status_code == 200
            except Exception:
                return False

    async def self_check(self):
        """Check if Temp-Mail API is working."""
        try:
            result = await self.create_mailbox()
            if result.get("email"):
                logger.info("✅ Temp-Mail self-check OK")
                # پاک‌سازی بعد از چک
                await self.delete_mailbox()
                return True
        except Exception as e:
            logger.error(f"❌ Temp-Mail self-check failed: {e}")
            raise
        return False
