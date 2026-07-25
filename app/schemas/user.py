from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


# Token schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
    type: str | None = None
    exp: int | None = None


# User Address Schemas
class UserAddressBase(BaseModel):
    street: str
    city: str
    state: str
    zip: str
    is_default: bool = False


class UserAddressCreate(UserAddressBase):
    pass


class UserAddressUpdate(BaseModel):
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    is_default: bool | None = None


class UserAddressOut(UserAddressBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.CUSTOMER
    is_active: bool = True
    is_email_verified: bool = False


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.CUSTOMER


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class UserOut(UserBase):
    id: int
    created_at: datetime
    addresses: list[UserAddressOut] = []

    model_config = ConfigDict(from_attributes=True)
