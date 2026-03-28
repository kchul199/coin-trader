from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext
import pyotp

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, str]:
    """
    Create a JWT access token.

    Args:
        data: Dictionary containing claims to encode in the token
        expires_delta: Optional timedelta for token expiration

    Returns:
        Tuple of (token, jti) where jti is the JWT ID for blacklisting
    """
    to_encode = data.copy()
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": jti,
    })
    token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload as dictionary

    Raises:
        JWTError: If token is invalid or expired
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


async def is_token_blacklisted(jti: str) -> bool:
    """
    Check if a token (by JTI) is blacklisted in Redis.

    Args:
        jti: JWT ID to check

    Returns:
        True if token is blacklisted, False otherwise
    """
    from app.core.redis_client import get_redis
    redis = await get_redis()
    return bool(await redis.get(f"jwt:blacklist:{jti}"))


async def blacklist_token(jti: str, expires_at: datetime) -> None:
    """
    Add a token to the Redis blacklist.

    Args:
        jti: JWT ID to blacklist
        expires_at: Token expiration datetime
    """
    from app.core.redis_client import get_redis
    redis = await get_redis()
    ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    if ttl > 0:
        await redis.setex(f"jwt:blacklist:{jti}", ttl, "1")


# 2FA (TOTP) helpers
def generate_totp_secret() -> str:
    """
    Generate a new TOTP secret.

    Returns:
        Base32-encoded random secret string
    """
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """
    Get the otpauth:// URI for 2FA setup (used for QR codes).

    Args:
        secret: TOTP secret
        email: User email (for display in authenticator apps)

    Returns:
        otpauth:// URI string
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name="CoinTrader")


def verify_totp(secret: str, code: str) -> bool:
    """
    Verify a TOTP code against a secret.

    Args:
        secret: TOTP secret
        code: 6-digit TOTP code to verify

    Returns:
        True if code is valid, False otherwise
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
