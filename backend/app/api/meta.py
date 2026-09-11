"""Health-Check, Metadaten und Ersteinrichtung."""

from __future__ import annotations

from hmac import compare_digest

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from app import __version__
from app.api.deps import DB, Res, client_ip
from app.models import Area, User
from app.schemas.auth import MetaOut, SetupIn, UserOut
from app.security.passwords import PasswordPolicyError, check_password_policy, hash_password_async
from app.security.sessions import create_session, set_session_cookies
from app.services import audit

router = APIRouter(prefix="/api", tags=["meta"])

SETUP_LOCK_ID = 7_310_001
DEFAULT_AREAS = (
    ("Arbeit", "#2563eb", "briefcase", 0),
    ("Privat", "#16a34a", "home", 1),
)


@router.get("/health")
async def health(db: DB, res: Res) -> JSONResponse:
    checks = {"database": "ok", "redis": "ok"}
    try:
        await db.execute(text("select 1"))
    except Exception:
        checks["database"] = "error"
    try:
        await res.redis.ping()
    except Exception:
        checks["redis"] = "error"
    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ok" if healthy else "error", "version": __version__, **checks},
        status_code=200 if healthy else 503,
    )


async def _setup_required(db: DB) -> bool:
    return not await db.scalar(select(func.count()).select_from(User))


@router.get("/meta", response_model=MetaOut)
async def meta(db: DB, res: Res) -> MetaOut:
    return MetaOut(
        version=__version__, setup_required=await _setup_required(db), rp_id=res.settings.rp_id
    )


@router.post("/setup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def setup(body: SetupIn, request: Request, response: Response, db: DB, res: Res) -> User:
    ip = client_ip(request)
    await res.limiter.enforce("setup", ip or "unknown", limit=10, window=600)

    expected = res.settings.setup_token
    if expected is None and res.settings.environment == "production":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Einrichtungscode fehlt. Auf dem Server 'todoch setup-code' ausführen.",
        )
    if expected is not None and not compare_digest(
        (body.setup_token or "").encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Der Einrichtungscode ist falsch.")

    # Verhindert, dass zwei gleichzeitige Anfragen beide einen Admin anlegen.
    await db.execute(select(func.pg_advisory_xact_lock(SETUP_LOCK_ID)))
    if not await _setup_required(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Todoch ist bereits eingerichtet.")

    try:
        check_password_policy(body.password, email=body.email, display_name=body.display_name)
    except PasswordPolicyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc

    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=await hash_password_async(body.password),
        is_admin=True,
        timezone=body.timezone,
        locale=body.locale,
    )
    db.add(user)
    await db.flush()
    for name, color, icon, order in DEFAULT_AREAS:
        db.add(Area(owner_id=user.id, name=name, color=color, icon=icon, sort_order=order))

    _, token = await create_session(
        db, user, res.settings, method="password", ip=ip,
        user_agent=request.headers.get("user-agent"),
    )  # fmt: skip
    audit.record(db, "setup.completed", user_id=user.id, ip=ip)
    await db.commit()
    set_session_cookies(response, token, res.settings)
    return user
