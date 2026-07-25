from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.order import OrderStatus, ReturnStatus
from app.schemas.product import ProductVariantOut


# Warehouse Schemas
class WarehouseBase(BaseModel):
    name: str
    address: dict[str, Any]
    is_active: bool = True


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseOut(WarehouseBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Order Item Schemas
class OrderItemOut(BaseModel):
    id: int
    product_variant_id: int
    quantity: int
    unit_price: float
    variant: ProductVariantOut

    model_config = ConfigDict(from_attributes=True)


# Order Return Schemas
class OrderReturnCreate(BaseModel):
    order_item_id: int
    quantity: int
    reason: str


class OrderReturnOut(BaseModel):
    id: int
    order_id: int
    order_item_id: int
    status: ReturnStatus
    reason: str
    quantity: int
    refund_amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Order Fulfillment Schemas
class OrderFulfillmentCreate(BaseModel):
    warehouse_id: int
    status: str
    tracking_number: str | None = None
    carrier: str | None = None


class OrderFulfillmentOut(BaseModel):
    id: int
    order_id: int
    warehouse_id: int
    status: str
    tracking_number: str | None = None
    carrier: str | None = None
    warehouse: WarehouseOut

    model_config = ConfigDict(from_attributes=True)


# Order Schemas
class OrderCreate(BaseModel):
    shipping_address: dict[str, Any]
    billing_address: dict[str, Any]


class OrderUpdateStatus(BaseModel):
    status: OrderStatus


class OrderOut(BaseModel):
    id: int
    order_number: str
    user_id: int
    status: OrderStatus
    subtotal: float
    shipping_amount: float
    tax_amount: float
    discount_amount: float
    total: float
    shipping_address: dict[str, Any]
    billing_address: dict[str, Any]
    created_at: datetime
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    items: list[OrderItemOut] = []
    fulfillments: list[OrderFulfillmentOut] = []
    returns: list[OrderReturnOut] = []

    model_config = ConfigDict(from_attributes=True)
