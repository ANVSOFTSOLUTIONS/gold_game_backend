import secrets
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_otp() -> str:
    """6-digit numeric OTP, e.g. '042917'."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code: str) -> str:
    return pwd_context.hash(code)


def verify_otp_hash(code: str, code_hash: str) -> bool:
    return pwd_context.verify(code, code_hash)


def create_access_token(user_id: int, mobile: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "mobile": mobile, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
