from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
import uuid


class UserRegister(BaseModel):
    """User registration request schema."""
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """User login request schema."""
    email: str
    password: str
    totp_code: Optional[str] = None  # 2FA code (if 2FA is enabled)


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """User response schema."""
    id: uuid.UUID
    email: str
    is_active: bool
    has_2fa: bool  # Whether 2FA is enabled
    created_at: datetime

    class Config:
        from_attributes = True


class TotpSetupResponse(BaseModel):
    """2FA setup response with secret and QR code URI."""
    secret: str
    qr_uri: str  # otpauth:// URI for QR code


class TotpVerifyRequest(BaseModel):
    """2FA verification request."""
    totp_code: str = Field(..., min_length=6, max_length=6)


class LogoutRequest(BaseModel):
    """Logout request schema."""
    pass  # JWT is in Authorization header
