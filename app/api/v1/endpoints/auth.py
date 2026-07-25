from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, reusable_oauth2
from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.crud.user import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user,
)
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import (
    ChangePassword,
    Token,
    TokenPayload,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_in: UserCreate,
) -> User:
    """
    Register a new user.
    """
    user = await get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
    return await create_user(db, obj_in=user_in)


@router.post("/login", response_model=Token)
async def login(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_in: UserCreate,  # Email and password
) -> Token:
    """
    OAuth2 compatible token login, retrieve access and refresh tokens.
    """
    user = await authenticate_user(db, email=user_in.email, password=user_in.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    token_credentials: Annotated[
        HTTPAuthorizationCredentials, Depends(reusable_oauth2)
    ],
) -> Token:
    """
    Refresh access token using a valid refresh token.
    """
    token = token_credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)

        if token_data.type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type, refresh token required",
            )

        user_id_str = token_data.sub
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from None

    user = await get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)
    return Token(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserOut)
async def read_user_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get current active user.
    """
    return current_user


@router.put("/me", response_model=UserOut)
async def update_user_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_in: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Update current active user profile.
    """
    # Prevent users from changing their own role to ADMIN this way
    if user_in.role is not None:
        user_in.role = current_user.role

    # Check email uniqueness if email is being updated
    if user_in.email is not None and user_in.email != current_user.email:
        existing = await get_user_by_email(db, email=user_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )

    return await update_user(db, db_obj=current_user, obj_in=user_in)


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    db: Annotated[AsyncSession, Depends(get_db)],
    password_in: ChangePassword,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """
    Change password for the current active user.
    """
    if not verify_password(password_in.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )
    user_update = UserUpdate(password=password_in.new_password)
    await update_user(db, db_obj=current_user, obj_in=user_update)
    return {"message": "Password updated successfully"}
