from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserAddress
from app.schemas.user import UserAddressCreate, UserCreate, UserUpdate


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.addresses))
    )
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email).options(selectinload(User.addresses))
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, obj_in: UserCreate) -> User:
    hashed_password = get_password_hash(obj_in.password)
    db_obj = User(
        email=obj_in.email,
        hashed_password=hashed_password,
        role=obj_in.role,
    )
    db.add(db_obj)
    await db.flush()
    # Eagerly load empty addresses relation
    await db.refresh(db_obj, ["addresses"])
    return db_obj


async def update_user(db: AsyncSession, db_obj: User, obj_in: UserUpdate) -> User:
    update_data = obj_in.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        hashed_password = get_password_hash(update_data["password"])
        db_obj.hashed_password = hashed_password
        del update_data["password"]

    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)
    return db_obj


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user_address(
    db: AsyncSession, user_id: int, obj_in: UserAddressCreate
) -> UserAddress:
    # If this address is set to default, we must unset any other default
    # addresses for this user
    if obj_in.is_default:
        await db.execute(
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .where(UserAddress.is_default.is_(True))
        )
        # Unset default for existing addresses
        # Wait, let's query them and update or execute a direct update
        from sqlalchemy import update

        await db.execute(
            update(UserAddress)
            .where(UserAddress.user_id == user_id)
            .values(is_default=False)
        )

    db_obj = UserAddress(**obj_in.model_dump(), user_id=user_id)
    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)
    return db_obj
