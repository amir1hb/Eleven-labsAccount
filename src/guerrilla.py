import httpx
import random
import string
from loguru import logger

class GuerrillaMailClient:
    def __init__(self):
        self.base_url = "https://api.guerrillamail.com/ajax.php"
        self.email = None
        self.sid_token = None

    async def create_mailbox(self, domain: str = None) -> dict:
        """ساخت یک صندوق پستی موقت جدید"""
        # تولید ایمیل تصادفی
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        if domain:
            email = f"{username}@{domain}"
        else:
            # دامنه‌های پیش‌فرض Guerrilla Mail
            domains = ["guerrillamail.com", "guerrillamail.net", "guerrillamail.org"]
            email = f"{username}@{random.choice(domains)}"

        # درخواست به Guerrilla Mail برای ایجاد صندوق
        params = {
            "f": "set_email_user",
            "email_user": username,
            "lang": "en"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self.base_url, params=params)
            data = resp.json()
            
        if data.get("email"):
            self.email = data["email"]
            self.sid_token = data.get("sid_token")
            logger.info(f"✅ Guerrilla mailbox created: {self.email}")
            return {"email": self.email, "sid_token": self.sid_token}
        else:
            raise Exception("Failed to create mailbox via Guerrilla Mail")

    async def list_messages(self) -> list:
        """دریافت لیست ایمیل‌های دریافتی"""
        if not self.sid_token:
            return []
        
        params = {
            "f": "fetch_email_list",
            "sid_token": self.sid_token
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self.base_url, params=params)
            data = resp.json()
            
        return data.get("list", [])

    async def get_message(self, email_id: str) -> dict:
        """دریافت محتوای یک ایمیل با شناسه"""
        if not self.sid_token:
            return {}
        
        params = {
            "f": "fetch_email",
            "sid_token": self.sid_token,
            "email_id": email_id
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self.base_url, params=params)
            data = resp.json()
            
        return data

    async def delete_mailbox(self) -> bool:
        """حذف صندوق پستی"""
        if not self.sid_token:
            return True
            
        params = {
            "f": "forget_me",
            "sid_token": self.sid_token
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self.base_url, params=params)
            data = resp.json()
            
        return data.get("success", False)

    async def self_check(self):
        """بررسی در دسترس بودن API (جایگزین PinMX self_check)"""
        try:
            result = await self.create_mailbox()
            if result.get("email"):
                logger.info("✅ Guerrilla Mail self-check OK")
                # پاک‌سازی بعد از چک
                await self.delete_mailbox()
                return True
        except Exception as e:
            logger.error(f"❌ Guerrilla Mail self-check failed: {e}")
            raise
        return False
