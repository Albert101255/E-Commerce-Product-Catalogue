from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.product import ProductVariantOut


class CartItemBase(BaseModel):
    product_variant_id: int
    quantity: int = 1


class CartItemCreate(CartItemBase):
    pass


class CartItemUpdate(BaseModel):
    quantity: int


class CartItemOut(CartItemBase):
    id: int
    cart_id: int
    price_at_add: float
    variant: ProductVariantOut

    model_config = ConfigDict(from_attributes=True)


class CartOut(BaseModel):
    id: int
    user_id: int
    expires_at: datetime
    items: list[CartItemOut] = []

    model_config = ConfigDict(from_attributes=True)
