from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, InvalidRefreshTokenError

TokenType = Literal["access", "refresh"]


class TokenClaims(BaseModel):
    """Validated claims shared by access and refresh JWTs."""

    model_config = ConfigDict(extra="ignore")

    sub: UUID
    type: TokenType
    jti: UUID
    iat: int
    exp: int


class PasswordService:
    """Argon2id password hashing and verification."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False


class TokenPair(BaseModel):
    """Access/refresh token pair returned by authentication operations."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class TokenService:
    """Create and validate signed JWTs using settings supplied by the application."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings

    def issue_pair(self, user_id: UUID) -> tuple[TokenPair, UUID]:
        now = datetime.now(UTC)
        access_expires = now + timedelta(minutes=self._settings.access_token_expire_minutes)
        refresh_expires = now + timedelta(days=self._settings.refresh_token_expire_days)
        refresh_jti = uuid4()
        access = self._encode(user_id, "access", uuid4(), now, access_expires)
        refresh = self._encode(user_id, "refresh", refresh_jti, now, refresh_expires)
        return (
            TokenPair(
                access_token=access,
                refresh_token=refresh,
                expires_in=self._settings.access_token_expire_minutes * 60,
            ),
            refresh_jti,
        )

    def decode_access(self, token: str) -> TokenClaims:
        claims = self._decode(token)
        if claims.type != "access":
            raise AuthenticationError("Authentication failed")
        return claims

    def decode_refresh(self, token: str, *, allow_expired: bool = False) -> TokenClaims:
        try:
            claims = self._decode(token, verify_exp=not allow_expired)
        except AuthenticationError as exc:
            raise InvalidRefreshTokenError("Invalid refresh token") from exc
        if claims.type != "refresh":
            raise InvalidRefreshTokenError("Invalid refresh token")
        return claims

    def _encode(
        self,
        user_id: UUID,
        token_type: TokenType,
        jti: UUID,
        issued_at: datetime,
        expires_at: datetime,
    ) -> str:
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "type": token_type,
            "jti": str(jti),
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(
            payload, self._settings.secret_key, algorithm=self._settings.jwt_algorithm
        )

    def _decode(self, token: str, *, verify_exp: bool = True) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._settings.secret_key,
                algorithms=[self._settings.jwt_algorithm],
                options={"verify_exp": verify_exp},
            )
            return TokenClaims.model_validate(payload)
        except (jwt.InvalidTokenError, ValidationError, ValueError, TypeError) as exc:
            raise AuthenticationError("Authentication failed") from exc
