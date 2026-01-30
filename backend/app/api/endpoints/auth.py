from datetime import timedelta
from typing import Any
import logging
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, User as UserSchema, Token

router = APIRouter()

logger = logging.getLogger(__name__)


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str


@router.options("/login")
async def options_login() -> Response:
    return Response(status_code=204)


@router.options("/register")
async def options_register() -> Response:
    return Response(status_code=204)

@router.post("/login", response_model=Token)
async def login_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    login_value = (form_data.username or "").strip()
    result = await db.execute(select(User).where(User.email == login_value))
    user = result.scalars().first()

    if not user and "@" not in login_value:
        domain = settings.DEFAULT_ADMIN_EMAIL.split("@")[1] if settings.DEFAULT_ADMIN_EMAIL and "@" in settings.DEFAULT_ADMIN_EMAIL else "admin123.com"
        fallback_email = f"{login_value}@{domain}"
        result = await db.execute(select(User).where(User.email == fallback_email))
        user = result.scalars().first()

        if not user and login_value == (settings.DEFAULT_ADMIN_EMAIL.split("@")[0] if settings.DEFAULT_ADMIN_EMAIL else ""):
            result = await db.execute(select(User).where(User.email == settings.DEFAULT_ADMIN_EMAIL))
            user = result.scalars().first()
    
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


@router.post("/change-password", response_model=dict)
async def change_password(
    payload: ChangePasswordPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if not security.verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")

    current_user.hashed_password = security.get_password_hash(payload.new_password)
    db.add(current_user)
    await db.commit()
    return {"status": "ok"}

@router.post("/register", response_model=UserSchema)
async def register_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """
    Create new user.
    """
    result = await db.execute(select(User).where(User.email == user_in.email))
    user = result.scalars().first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    
    try:
        user = User(
            email=user_in.email,
            hashed_password=security.get_password_hash(user_in.password),
            full_name=user_in.full_name,
            role=UserRole.USER,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    except Exception:
        await db.rollback()
        logger.exception("Registration failed")
        raise HTTPException(status_code=500, detail="Registration failed")

@router.get("/me", response_model=UserSchema)
async def read_users_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user
