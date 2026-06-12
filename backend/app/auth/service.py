"""Password, session, and MT5-account ownership service."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.persistence.repositories import (
    Mt5AccountRepository,
    Mt5ConfigRepository,
    UserRepository,
    UserSessionRepository,
)

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32


class AuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthContext:
    user_id: int | None
    mt5_login: int | None
    display_name: str
    role: str
    mt5_account_id: int | None
    mt5_server: str | None
    account_type: str | None
    auth_source: str
    session_token_hash: str | None = None

    @property
    def actor_name(self) -> str:
        if self.mt5_login is not None:
            return f"mt5:{self.mt5_login}"
        return self.display_name


@dataclass(frozen=True)
class SessionCredentials:
    token: str
    csrf_token: str
    expires_at: datetime
    context: AuthContext


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return (
        f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$"
        f"{salt.hex()}${derived.hex()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.accounts = Mt5AccountRepository(session)
        self.sessions = UserSessionRepository(session)

    def bootstrap_required(self) -> bool:
        return self.settings.user_auth_enabled and self.users.count() == 0

    def bootstrap(
        self,
        *,
        mt5_login: int,
        app_password: str,
        display_name: str,
        mt5_server: str,
        account_type: str,
    ) -> SessionCredentials:
        if not self.settings.user_auth_enabled:
            raise AuthError("User authentication is disabled")
        if not self.settings.auth_bootstrap_enabled:
            raise AuthError("First-user bootstrap is disabled")
        if self.session.get_bind().dialect.name == "postgresql":
            # Serialize first-user creation across backend workers.
            self.session.execute(text("SELECT pg_advisory_xact_lock(84726101)"))
        if self.users.count() != 0:
            raise AuthError("The first application user already exists")
        try:
            with self.session.begin_nested():
                user = self.users.create(
                    mt5_login=mt5_login,
                    display_name=display_name.strip(),
                    password_hash=hash_password(app_password),
                    is_admin=True,
                )
                account = self.accounts.create(
                    owner_user_id=user.id,
                    login=mt5_login,
                    server=mt5_server,
                    account_type=account_type,
                    display_name=f"{mt5_server.strip()} / {mt5_login}",
                )
                Mt5ConfigRepository(self.session).bind_account(account.id)
        except IntegrityError as exc:
            raise AuthError("MT5 login or account is already registered") from exc
        return self._create_session(user.id)

    def login(self, *, mt5_login: int, app_password: str) -> SessionCredentials:
        user = self.users.get_by_mt5_login(mt5_login)
        now = datetime.now(timezone.utc)
        if user is None or user.status != "ACTIVE":
            raise AuthError("Invalid MT5 login or app password")
        if user.locked_until is not None and _aware(user.locked_until) > now:
            raise AuthError("Account is temporarily locked after failed login attempts")
        if not verify_password(app_password, user.password_hash):
            user.failed_login_count += 1
            if user.failed_login_count >= self.settings.auth_max_failed_attempts:
                user.locked_until = now + timedelta(
                    minutes=self.settings.auth_lock_minutes
                )
                user.failed_login_count = 0
            self.session.flush()
            raise AuthError("Invalid MT5 login or app password")
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        self.session.flush()
        return self._create_session(user.id)

    def _create_session(self, user_id: int) -> SessionCredentials:
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.settings.auth_session_hours
        )
        self.sessions.create(
            token_hash=_sha256(token),
            user_id=user_id,
            csrf_hash=_sha256(csrf_token),
            expires_at=expires_at,
        )
        context = self.context_for_token(token)
        if context is None:
            raise AuthError("Could not create user session")
        return SessionCredentials(
            token=token,
            csrf_token=csrf_token,
            expires_at=expires_at,
            context=context,
        )

    def context_for_token(self, token: str) -> AuthContext | None:
        if not token:
            return None
        token_hash = _sha256(token)
        row = self.sessions.get(token_hash)
        now = datetime.now(timezone.utc)
        if (
            row is None
            or row.revoked_at is not None
            or _aware(row.expires_at) <= now
        ):
            return None
        user = self.users.get(row.user_id)
        if user is None or user.status != "ACTIVE":
            return None
        account = self.accounts.get_primary_for_user(user.id)
        if account is None:
            return None
        if (now - _aware(row.last_seen_at)).total_seconds() >= 300:
            row.last_seen_at = now
            self.session.flush()
        return AuthContext(
            user_id=user.id,
            mt5_login=user.mt5_login,
            display_name=user.display_name,
            role="owner" if user.is_admin else "operator",
            mt5_account_id=account.id,
            mt5_server=account.server,
            account_type=account.account_type,
            auth_source="session",
            session_token_hash=token_hash,
        )

    def validate_csrf(self, token: str, csrf_token: str) -> bool:
        row = self.sessions.get(_sha256(token))
        return bool(
            row
            and row.revoked_at is None
            and csrf_token
            and hmac.compare_digest(row.csrf_hash, _sha256(csrf_token))
        )

    def logout(self, token: str) -> None:
        if token:
            self.sessions.revoke(_sha256(token))
