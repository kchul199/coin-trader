from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
import uuid

from app.dependencies import get_current_user, get_db
from app.core.redis_client import get_redis
from app.models.user import User
from app.models.jwt_blacklist import JWTBlacklist
from app.schemas.auth import (
    UserRegister, UserLogin, TokenResponse, UserResponse,
    TotpSetupResponse, TotpVerifyRequest,
)
from app.core.security import (
    hash_password, verify_password, create_access_token, decode_token,
    is_token_blacklisted, blacklist_token,
    generate_totp_secret, get_totp_uri, verify_totp,
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer()
TOTP_PENDING_PREFIX = "auth:2fa:pending:"


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.

    Args:
        data: User registration data
        db: Database session

    Returns:
        Created user data
    """
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다.")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        has_2fa=bool(user.totp_secret),
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Login user and return JWT token.

    Args:
        data: User login credentials
        db: Database session

    Returns:
        Access token with expiration
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="비활성화된 계정입니다.")

    # 2FA verification
    if user.totp_secret:
        if not data.totp_code:
            raise HTTPException(status_code=422, detail="2FA 코드가 필요합니다.")
        if not verify_totp(user.totp_secret, data.totp_code):
            raise HTTPException(status_code=401, detail="2FA 코드가 올바르지 않습니다.")

    expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    token, jti = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=timedelta(minutes=expire_minutes),
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout user by blacklisting the JWT token.

    Args:
        credentials: HTTP Bearer token
        current_user: Current authenticated user
        db: Database session
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        exp = datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)

        if jti:
            await blacklist_token(jti, exp)

            # Audit log to database
            blacklist = JWTBlacklist(
                jti=uuid.UUID(jti),
                user_id=current_user.id,
                reason="logout",
                expires_at=exp,
            )
            db.add(blacklist)
            await db.commit()
    except Exception:
        pass  # Always treat logout as success


@router.post("/2fa/setup", response_model=TotpSetupResponse)
async def setup_2fa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Start 2FA setup by generating a TOTP secret and QR code URI.

    The secret is temporarily saved but not activated until verify_2fa is called.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Secret and QR code URI for authenticator app
    """
    secret = generate_totp_secret()
    pending_key = f"{TOTP_PENDING_PREFIX}{current_user.id}"
    await redis.setex(pending_key, 600, secret)

    qr_uri = get_totp_uri(secret, current_user.email)
    return TotpSetupResponse(secret=secret, qr_uri=qr_uri)


@router.post("/2fa/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_2fa(
    data: TotpVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Verify TOTP code and confirm 2FA activation.

    Args:
        data: TOTP verification code (6 digits)
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If 2FA setup not started or code is invalid
    """
    pending_key = f"{TOTP_PENDING_PREFIX}{current_user.id}"
    pending_secret = await redis.get(pending_key)

    if not pending_secret:
        raise HTTPException(status_code=400, detail="2FA 설정이 시작되지 않았습니다.")

    if not verify_totp(pending_secret, data.totp_code):
        raise HTTPException(status_code=401, detail="2FA 코드가 올바르지 않습니다.")

    current_user.totp_secret = pending_secret
    await db.commit()
    await redis.delete(pending_key)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's information.

    Args:
        current_user: Current authenticated user

    Returns:
        User response data
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        has_2fa=bool(current_user.totp_secret),
        created_at=current_user.created_at,
    )
