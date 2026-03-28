# 2FA Authentication Implementation Guide

## Overview
This document describes the complete 2FA (Two-Factor Authentication) and JWT blacklisting implementation for the coin trading bot authentication system.

## Implementation Status
- ✓ `/app/schemas/auth.py` - Updated with 2FA schemas
- ✓ `/app/core/security.py` - Complete rewrite with JWT + 2FA utilities
- ✓ `/app/api/v1/auth.py` - 6 endpoints with full 2FA support
- ✓ `/app/dependencies.py` - JWT blacklist validation
- ✓ Requirements already contain: `pyotp==2.9.0`, `qrcode[pil]==7.4.2`

## Architecture

### JWT Token Flow
```
1. User Login → Validate credentials → Generate JWT with JTI
2. JWT includes: sub (user_id), email, exp, iat, jti
3. Protected requests check token validity and blacklist status
4. Logout → Add JTI to Redis blacklist with TTL
```

### 2FA Flow
```
1. User calls POST /auth/2fa/setup → Get secret + QR code
2. User scans QR code with authenticator app (Google Authenticator, Authy, etc.)
3. User provides TOTP code → POST /auth/2fa/verify
4. Future logins require TOTP code in addition to password
```

## API Endpoints

### 1. User Registration
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Responses:**
- `201 Created` - Success
- `409 Conflict` - Email already registered

**Returns:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "is_active": true,
  "has_2fa": false,
  "created_at": "2024-01-15T10:30:00+00:00"
}
```

### 2. User Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "totp_code": "123456"  // Optional, required if 2FA enabled
}
```

**Responses:**
- `200 OK` - Success
- `401 Unauthorized` - Invalid credentials or TOTP
- `403 Forbidden` - Inactive account
- `422 Unprocessable Entity` - TOTP required but not provided

**Returns:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 3. Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Responses:**
- `200 OK` - Success
- `401 Unauthorized` - Invalid/blacklisted token

**Returns:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "is_active": true,
  "has_2fa": true,
  "created_at": "2024-01-15T10:30:00+00:00"
}
```

### 4. Setup 2FA
```http
POST /api/v1/auth/2fa/setup
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Responses:**
- `200 OK` - Success
- `401 Unauthorized` - Invalid token

**Returns:**
```json
{
  "secret": "JBSWY3DPEBLW64TMMQ7A4A3I",
  "qr_uri": "otpauth://totp/CoinTrader:user@example.com?secret=JBSWY3DPEBLW64TMMQ7A4A3I&issuer=CoinTrader"
}
```

**Client Implementation:**
1. Display QR code to user (using qr_uri)
2. User scans with authenticator app
3. Call verify endpoint with code from app

### 5. Verify 2FA
```http
POST /api/v1/auth/2fa/verify
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "totp_code": "123456"
}
```

**Responses:**
- `204 No Content` - Success
- `400 Bad Request` - 2FA setup not initiated
- `401 Unauthorized` - Invalid TOTP code or token
- `422 Unprocessable Entity` - Invalid code format (not 6 digits)

### 6. Logout
```http
POST /api/v1/auth/logout
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Responses:**
- `204 No Content` - Always succeeds (secure logout pattern)

**Side Effects:**
- Token JTI added to Redis blacklist
- Audit log entry created in `jwt_blacklist` table

## Database Schema

### User Table (existing)
```sql
-- Already has these fields:
- id (UUID, primary key)
- email (String, unique, indexed)
- password_hash (String)
- totp_secret (String, nullable)  -- 2FA secret
- is_active (Boolean)
- created_at (DateTime)
- updated_at (DateTime)
```

### JWT Blacklist Table (existing)
```sql
-- Audit trail of blacklisted tokens:
- jti (UUID, primary key)
- user_id (UUID, foreign key)
- reason (String, nullable)
- expires_at (DateTime)
- created_at (DateTime)
```

## Redis Schema

### JWT Blacklist Keys
```
Key: jwt:blacklist:{jti}
Value: "1"
TTL: token expiration time
```

Example: `jwt:blacklist:3fa85f64-5717-4562-b3fc-2c963f66afa6` → expires at token expiration

## Security Considerations

### Password Security
- Minimum 8 characters required
- Bcrypt hashing with automatic cost adjustment
- Never log or transmit plain passwords

### JWT Security
- `HS256` algorithm (HMAC-SHA256)
- JTI (JWT ID) claim enables token revocation
- TTL-based automatic cleanup from Redis
- Issued-at (`iat`) timestamp for additional validation

### 2FA Security
- TOTP (Time-based One-Time Password) algorithm per RFC 6238
- 30-second time window with ±1 window tolerance
- Industry-standard (compatible with Google Authenticator, Authy, etc.)
- Secret stored as plaintext in database (should be encrypted in production)

### Token Blacklisting
- Redis for high-performance revocation checks
- Automatic TTL cleanup (no manual purging needed)
- Database audit trail for compliance
- Immediate logout effect

## Environment Configuration

Add to `.env`:
```bash
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Redis Configuration (required for blacklist)
REDIS_URL=redis://localhost:6379/0

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost/cointrader
```

## Testing Flow

### Complete User Journey
```bash
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123"
  }'

# 2. Login (without 2FA)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123"
  }'

# 3. Setup 2FA (requires token)
TOKEN="eyJhbGc..."
curl -X POST http://localhost:8000/api/v1/auth/2fa/setup \
  -H "Authorization: Bearer $TOKEN"

# 4. Verify 2FA (requires token)
curl -X POST http://localhost:8000/api/v1/auth/2fa/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"totp_code": "123456"}'

# 5. Get user info (verify 2FA enabled)
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"

# 6. Logout
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer $TOKEN"

# 7. Try using old token (should fail)
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Login with 2FA
```bash
# User must provide totp_code
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123",
    "totp_code": "123456"
  }'
```

## Error Handling

### Common Error Responses

**401 Unauthorized**
- Invalid/expired token
- Blacklisted token
- Invalid credentials
- Missing TOTP code when required

**403 Forbidden**
- Inactive user account

**409 Conflict**
- Email already registered

**422 Unprocessable Entity**
- Invalid TOTP code format (not 6 digits)
- Missing required fields
- Password too short (<8 characters)

## Migration Notes

### From Old Auth System
- `create_access_token()` now returns tuple `(token, jti)`
- Update all token generation calls:
  ```python
  # Old
  token = create_access_token(data)

  # New
  token, jti = create_access_token(data)
  ```

- Import `get_current_user` from `app.dependencies`, not directly from security
- JWT verification now checks blacklist automatically

### Breaking Changes
- `verify_token()` renamed to `decode_token()`
- `oauth2_scheme` moved to `dependencies.py` as `bearer_scheme`
- All protected endpoints now require `HTTPBearer` scheme

## Performance Considerations

### Redis Blacklist
- Typical key size: ~40 bytes
- Check operation: O(1) - instant
- TTL cleanup: automatic (no manual management)
- Estimated storage for 10,000 active sessions: ~400KB

### Database Audit Log
- Optional (only written on logout)
- Can be archived to separate table if needed
- No impact on normal API performance

## Future Enhancements

1. **TOTP Secret Encryption**
   - Encrypt `totp_secret` in database
   - Use Fernet or AES-256

2. **Backup Codes**
   - Generate recovery codes during 2FA setup
   - Allow 2FA bypass if phone lost

3. **Session Management**
   - Track active sessions per user
   - Allow selective token revocation
   - Device management (name, last used)

4. **Rate Limiting**
   - Limit login attempts (after 5 failures)
   - Limit TOTP attempts (after 3 failures)

5. **Email Verification**
   - Send verification email on registration
   - Require email confirmation before login

6. **Security Audit Logging**
   - Log all auth events
   - Track IP addresses
   - Detect suspicious patterns

## Files Modified
- `/app/schemas/auth.py` (52 lines)
- `/app/core/security.py` (133 lines)
- `/app/api/v1/auth.py` (206 lines)
- `/app/dependencies.py` (71 lines)

## Support
For issues or questions, refer to:
- OAuth 2.0: https://tools.ietf.org/html/rfc6749
- JWT: https://tools.ietf.org/html/rfc7519
- TOTP: https://tools.ietf.org/html/rfc6238
