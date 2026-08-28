from secrets import token_urlsafe
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    InvalidRefreshTokenError,
    UserAlreadyExistsError,
)
from app.core.security import PasswordService, TokenPair, TokenService
from app.modules.auth.domain import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.session_store import SessionStore


class AuthService:
    """Application use cases for registration and token-based authentication."""

    def __init__(
        self,
        user_repository: UserRepository,
        session_store: SessionStore,
        token_service: TokenService,
        password_service: PasswordService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._users = user_repository
        self._sessions = session_store
        self._tokens = token_service
        self._passwords = password_service or PasswordService()
        self._settings = settings or token_service.settings
        self._dummy_hash = self._passwords.hash(token_urlsafe(32))

    async def register(self, username: str, email: str, password: str) -> User:
        normalized_email = email.lower()
        if await self._users.get_by_username(username) is not None:
            raise UserAlreadyExistsError("Username or email already exists")
        if await self._users.get_by_email(normalized_email) is not None:
            raise UserAlreadyExistsError("Username or email already exists")
        user = User.new(
            username=username,
            email=normalized_email,
            password_hash=self._passwords.hash(password),
        )
        return await self._users.create(user)

    async def login(self, account: str, password: str) -> TokenPair:
        user = (
            await self._users.get_by_email(account.lower())
            if "@" in account
            else await self._users.get_by_username(account)
        )
        valid_password = self._passwords.verify(
            user.password_hash if user is not None else self._dummy_hash,
            password,
        )
        if user is None or not user.is_active or not valid_password:
            raise AuthenticationError("Authentication failed")
        return await self._issue_tokens(user.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        claims = self._tokens.decode_refresh(refresh_token)
        session_user_id = await self._sessions.consume_refresh_session(claims.jti)
        if session_user_id != claims.sub:
            raise InvalidRefreshTokenError("Invalid refresh token")
        user = await self._users.get_by_id(claims.sub)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError("Invalid refresh token")
        return await self._issue_tokens(user.id)

    async def logout(self, refresh_token: str) -> None:
        claims = self._tokens.decode_refresh(refresh_token, allow_expired=True)
        await self._sessions.revoke_refresh_session(claims.jti, self._refresh_ttl_seconds)

    async def current_user(self, access_token: str) -> User:
        claims = self._tokens.decode_access(access_token)
        user = await self._users.get_by_id(claims.sub)
        if user is None or not user.is_active:
            raise AuthenticationError("Authentication failed")
        return user

    @property
    def _refresh_ttl_seconds(self) -> int:
        return self._settings.refresh_token_expire_days * 24 * 60 * 60

    async def _issue_tokens(self, user_id: UUID) -> TokenPair:
        pair, refresh_jti = self._tokens.issue_pair(user_id)
        await self._sessions.save_refresh_session(
            refresh_jti, user_id, self._refresh_ttl_seconds
        )
        return pair
