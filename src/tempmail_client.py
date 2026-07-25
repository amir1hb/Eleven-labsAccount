import asyncio
import random
import string
from typing import Optional, Dict, Any, List

import httpx
from loguru import logger


class TempMailClient:
    def __init__(self, email: Optional[str] = None, token: Optional[str] = None):
        self.base_url = "https://api.internal.temp-mail.io/api/v3"
        self.email = email
        self.token = token

    async def create_mailbox(self) -> Dict[str, str]:
        if self.email and self.token:
            logger.info(f"Using existing mailbox: {self.email}")
            return {"email": self.email, "token": self.token}

        name_length = 10
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=name_length))

        domains = [
            "ozsaip.com",
            "ruutukf.com",
            "mkzaso.com",
            "yzcalo.com",
            "wnbaldwy.com",
            "bltiwd.com",
            "xkxkud.com",
            "bwmyga.com",
            "lnovic.com",
            "mrotzis.com",
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
                    return {"email": self.email, "token": self.token}
                else:
                    raise Exception(f"Failed to create mailbox: {response.status_code} {response.text}")
            except Exception as e:
                raise Exception(f"Failed to create mailbox via Temp-Mail: {str(e)}")

    async def list_messages(self) -> List[Dict[str, Any]]:
        if not self.token:
            return []

        url = f"{self.base_url}/email/list"
        headers = {"Accept": "application/json"}
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
                    formatted = []
                    for msg in messages:
                        formatted.append({
                            "id": msg.get("id"),
                            "body": msg.get("body_html", "") or msg.get("body_text", ""),
                            "subject": msg.get("subject", ""),
                            "from": msg.get("from", {}).get("email", ""),
                            "to": msg.get("to", {}).get("email", ""),
                            "created_at": msg.get("created_at", "")
                        })
                    return formatted
                else:
                    logger.warning(f"List messages failed: {response.status_code}")
                    return []
            except Exception as e:
                logger.warning(f"List messages error: {e}")
                return []

    async def get_message(self, message_id: str) -> Dict[str, Any]:
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

    async def self_check(self) -> bool:
        try:
            result = await self.create_mailbox()
            if result.get("email"):
                logger.info("✅ Temp-Mail self-check OK")
                # Clean up after self-check
                await self.delete_mailbox()
                return True
        except Exception as e:
            logger.error(f"❌ Temp-Mail self-check failed: {e}")
            raise
        return False
