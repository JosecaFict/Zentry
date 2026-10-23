import json
import logging
import secrets
from dataclasses import asdict, dataclass
from html import escape
from uuid import uuid4

import httpx
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OtpRecord:
    user_id: int
    nonce: str
    digest: str
    attempts: int = 0


class RedisPasswordResetStore:
    _ATTEMPT_SCRIPT = """
local value = redis.call('GET', KEYS[1])
if not value then return nil end
local ttl = redis.call('TTL', KEYS[1])
local data = cjson.decode(value)
data.attempts = (data.attempts or 0) + 1
if data.attempts >= tonumber(ARGV[1]) then
  redis.call('DEL', KEYS[1])
else
  redis.call('SET', KEYS[1], cjson.encode(data), 'EX', ttl)
end
return cjson.encode(data)
"""

    def __init__(self, client: Redis) -> None:
        self.client = client

    @staticmethod
    def _otp_key(email_key: str) -> str:
        return f"auth:password-reset:otp:{email_key}"

    @staticmethod
    def _cooldown_key(email_key: str) -> str:
        return f"auth:password-reset:cooldown:{email_key}"

    @staticmethod
    def _verified_key(nonce: str) -> str:
        return f"auth:password-reset:verified:{nonce}"

    async def reserve_request(self, email_key: str, cooldown_seconds: int) -> bool:
        result = await self.client.set(
            self._cooldown_key(email_key),
            "1",
            ex=cooldown_seconds,
            nx=True,
        )
        return bool(result)

    async def save_otp(self, email_key: str, record: OtpRecord, ttl_seconds: int) -> None:
        await self.client.setex(self._otp_key(email_key), ttl_seconds, json.dumps(asdict(record)))

    async def take_attempt(self, email_key: str, max_attempts: int) -> OtpRecord | None:
        raw = await self.client.eval(
            self._ATTEMPT_SCRIPT,
            1,
            self._otp_key(email_key),
            max_attempts,
        )
        if raw is None:
            return None
        data = json.loads(raw)
        return OtpRecord(**data)

    async def delete_otp(self, email_key: str) -> None:
        await self.client.delete(self._otp_key(email_key))

    async def save_verified(self, nonce: str, user_id: int, ttl_seconds: int) -> None:
        await self.client.setex(self._verified_key(nonce), ttl_seconds, str(user_id))

    async def consume_verified(self, nonce: str) -> int | None:
        raw = await self.client.getdel(self._verified_key(nonce))
        return int(raw) if raw is not None else None


class BrevoEmailClient:
    endpoint = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, *, api_key: str, sender_email: str, sender_name: str) -> None:
        self.api_key = api_key
        self.sender_email = sender_email
        self.sender_name = sender_name

    async def send_password_reset_otp(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        otp: str,
        expires_minutes: int,
    ) -> None:
        safe_name = escape(recipient_name)
        safe_otp = escape(otp)
        html_content = f"""
<!doctype html>
<html lang="es">
  <body style="margin:0;background:#f7f6f3;color:#121418;font-family:Arial,sans-serif">
    <div style="max-width:560px;margin:0 auto;padding:40px 24px">
      <p style="margin:0 0 24px;color:#064fe8;font-weight:700;letter-spacing:.16em">
        ZENTRY · ACCESO SEGURO
      </p>
      <h1 style="margin:0 0 16px;font-size:30px">Recupera tu contraseña</h1>
      <p>Hola, {safe_name}. Usa este código para continuar:</p>
      <p style="margin:28px 0;font-size:36px;font-weight:700;letter-spacing:.18em">
        {safe_otp}
      </p>
      <p>
        El código vence en {expires_minutes} minutos.
        Si no solicitaste el cambio, ignora este mensaje.
      </p>
    </div>
  </body>
</html>
"""
        payload = {
            "sender": {"email": self.sender_email, "name": self.sender_name},
            "to": [{"email": recipient_email, "name": recipient_name}],
            "subject": "Código para recuperar tu contraseña",
            "htmlContent": html_content,
            "textContent": (
                f"Tu código de recuperación es {otp}. Vence en {expires_minutes} minutos."
            ),
            "tags": ["password-recovery"],
        }
        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status()
        logger.info("Password recovery email accepted by Brevo")


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_nonce() -> str:
    return str(uuid4())
