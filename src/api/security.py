"""Verified bearer identities; explicit local development accounts or configured OIDC."""
from __future__ import annotations

import base64
from collections import defaultdict, deque
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
import time

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse

PREFIX = 'HEALTH'
ROLES = {'staff', 'patient', 'admin'}
actor_token: ContextVar[str] = ContextVar("actor_token", default="")
router = APIRouter(prefix="/auth", tags=["Authentication"])


@dataclass(frozen=True)
class Principal:
    sub: str
    role: str
    expires_at: int
    account_version: int | None = None


def _setting(key: str, default: str = "") -> str:
    return os.getenv(f"{PREFIX}_AUTH_{key}", default)


def _unavailable() -> HTTPException:
    return HTTPException(503, "Authentication is not configured")


def _denied() -> HTTPException:
    return HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})


def auth_mode() -> str:
    mode = _setting("MODE", "oidc")
    if mode not in {"local", "oidc"}:
        raise _unavailable()
    if mode == "local" and (
        _setting("ENV") != "local"
        or os.getenv("APP_ENV", "").lower() in {"prod", "production"}
    ):
        raise _unavailable()
    return mode


def _secret() -> str:
    value = _setting("SECRET")
    if len(value) < 32 or value.lower().startswith(("replace", "change", "your-")):
        raise _unavailable()
    return value


def accounts() -> dict:
    path = _setting("ACCOUNTS_FILE")
    if not path:
        raise _unavailable()
    try:
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict):
            raise ValueError("Accounts must be an object")
        return data
    except (ValueError, OSError) as exc:
        raise _unavailable() from exc


def password_hash(password: str) -> str:
    if not 12 <= len(password) <= 512:
        raise ValueError("Password must have 12 to 512 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


_DUMMY_HASH = password_hash("unmatched-local-account-password")


def _password_matches(password: str, encoded: str) -> bool:
    if len(password) > 512:
        return False
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        salt_bytes = base64.b64decode(salt, validate=True)
        expected_bytes = base64.b64decode(expected, validate=True)
        if len(salt_bytes) != 16 or len(expected_bytes) != 32:
            return False
        actual = hashlib.scrypt(password.encode(), salt=salt_bytes, n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, expected_bytes)
    except (ValueError, TypeError):
        return False


def _valid_account(account: dict) -> bool:
    return (
        isinstance(account, dict)
        and account.get("active") is True
        and isinstance(account.get("sub"), str)
        and bool(account["sub"].strip())
        and account.get("role") in ROLES
        and isinstance(account.get("session_version"), int)
        and not isinstance(account.get("session_version"), bool)
    )


@lru_cache(maxsize=4)
def _jwks(url: str):
    return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300, timeout=5)


def verify_token(token: str) -> Principal:
    mode = auth_mode()
    required = ["sub", "exp", "iat", "iss", "aud"]
    try:
        if mode == "local":
            payload = jwt.decode(
                token, _secret(), algorithms=["HS256"],
                issuer=f"{PREFIX.lower()}-local", audience=f"{PREFIX.lower()}-api",
                options={"require": required + ["role", "ver"]},
            )
            account = next((a for a in accounts().values() if isinstance(a, dict) and a.get("sub") == payload["sub"]), None)
            if not _valid_account(account) or account["role"] != payload.get("role") or account["session_version"] != payload.get("ver"):
                raise _denied()
            subject, role, version = payload["sub"], payload["role"], payload["ver"]
        else:
            issuer, audience, url = _setting("ISSUER"), _setting("AUDIENCE"), _setting("JWKS_URL")
            if not issuer.startswith("https://") or not url.startswith("https://") or not audience:
                raise _unavailable()
            key = _jwks(url).get_signing_key_from_jwt(token).key
            payload = jwt.decode(token, key, algorithms=["RS256"], issuer=issuer, audience=audience, options={"require": required})
            subject = payload.get(_setting("IDENTITY_CLAIM", "sub"))
            role = payload.get(_setting("ROLE_CLAIM", "role"))
            version = None
        if not isinstance(subject, str) or not subject.strip() or role not in ROLES:
            raise _denied()
        return Principal(subject, role, int(payload["exp"]), version)
    except HTTPException:
        raise
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise _denied() from exc


def require_principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if principal is not None:
        return principal
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or not header[7:]:
        raise _denied()
    return verify_token(header[7:])


class BearerMiddleware:
    """Reject anonymous protected requests before JSON or file parsing."""
    def __init__(self, app, public=None):
        self.app = app
        self.public = public or (lambda p: p in {"/", "/health", "/auth/login", "/docs", "/redoc", "/openapi.json"} or p.startswith("/assets/"))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if path.startswith("/api/"):
            path = path[4:]
        if self.public(path):
            return await self.app(scope, receive, send)
        request = Request(scope)
        try:
            principal = require_principal(request)
        except HTTPException as exc:
            return await JSONResponse({"detail": exc.detail}, exc.status_code, headers=exc.headers)(scope, receive, send)
        scope.setdefault("state", {})["principal"] = principal
        context = actor_token.set(request.headers["authorization"][7:])
        try:
            await self.app(scope, receive, send)
        finally:
            actor_token.reset(context)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=512)


_attempts = defaultdict(deque)
_attempt_lock = threading.Lock()


@router.post("/login")
def login(body: Login, request: Request):
    if auth_mode() != "local":
        raise HTTPException(403, "Use the configured identity provider to sign in")
    secret = _secret()
    key = request.client.host if request.client else "unknown"
    with _attempt_lock:
        now = time.monotonic()
        history = _attempts[key]
        while history and history[0] <= now - 60:
            history.popleft()
        if len(history) >= 10:
            raise HTTPException(429, "Too many sign-in attempts; try again shortly")
        history.append(now)
        if len(_attempts) > 10000:
            for stale in [k for k, v in _attempts.items() if not v or v[-1] <= now - 60]:
                _attempts.pop(stale, None)
    account = accounts().get(body.username.strip())
    encoded = account.get("password_hash", _DUMMY_HASH) if isinstance(account, dict) else _DUMMY_HASH
    matches = _password_matches(body.password, encoded)
    if not matches or not _valid_account(account):
        raise _denied()
    now = int(time.time())
    payload = {"sub": account["sub"], "role": account["role"], "ver": account["session_version"], "iss": f"{PREFIX.lower()}-local", "aud": f"{PREFIX.lower()}-api", "iat": now, "exp": now + 900}
    return {"access_token": jwt.encode(payload, secret, algorithm="HS256"), "token_type": "bearer", "expires_in": 900}


@router.get("/me")
def me(request: Request):
    principal = require_principal(request)
    return {"sub": principal.sub, "role": principal.role}


def provision(path: Path, username: str, subject: str, role: str, password: str) -> None:
    if role not in ROLES or not subject.strip() or not username.strip():
        raise ValueError("Invalid account identity or role")
    data = json.loads(path.read_text()) if path.exists() else {}
    if any(a.get("sub") == subject for u, a in data.items() if u != username):
        raise ValueError("Each subject must have one account")
    version = int(data.get(username, {}).get("session_version", 0)) + 1
    data[username] = {"sub": subject, "role": role, "active": True, "session_version": version, "password_hash": password_hash(password)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, indent=2)
        os.replace(temp, path)
        os.chmod(path, 0o600)
    finally:
        temp.unlink(missing_ok=True)


if __name__ == "__main__":
    import argparse
    import getpass
    parser = argparse.ArgumentParser(description="Provision one local local account; no default credentials")
    parser.add_argument("file", type=Path)
    parser.add_argument("username")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--role", choices=sorted(ROLES), required=True)
    args = parser.parse_args()
    provision(args.file, args.username, args.subject, args.role, getpass.getpass("Password (minimum 12 characters): "))
    print("Account saved. Existing local sessions for this account are revoked.")
