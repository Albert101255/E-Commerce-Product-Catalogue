from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user, get_current_user
from app.crud.order import (
    create_order_from_cart,
    create_order_return,
    get_order_by_id,
    get_user_orders,
    update_order_status,
)
from app.db.base import get_db
from app.models.order import OrderStatus
from app.models.user import User, UserRole
from app.schemas.order import (
    OrderCreate,
    OrderOut,
    OrderReturnCreate,
    OrderReturnOut,
    OrderUpdateStatus,
)

router = APIRouter()


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def checkout(
    order_in: OrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Create a new order from items currently in the user's shopping cart.
    """
    try:
        return await create_order_from_cart(
            db, user_id=current_user.id, order_in=order_in
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None


@router.get("/", response_model=list[OrderOut])
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    List orders. Customers see their own, admins see all if we implement it,
    but here we list for the current active user.
    """
    return await get_user_orders(db, user_id=current_user.id)


@router.get("/{order_id}", response_model=OrderOut)
async def read_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Retrieve order details. Owner or admin access only.
    """
    order = await get_order_by_id(db, order_id=order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    if order.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this order",
        )
    return order


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: Annotated[User, Depends(get_admin_user)],
) -> Any:
    """
    Cancel an order. Admins only.
    """
    order = await get_order_by_id(db, order_id=order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    cancelable_states = [
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
        OrderStatus.REFUNDED,
    ]
    if order.status in cancelable_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel an order in '{order.status.value}' status",
        )
    return await update_order_status(db, order=order, new_status=OrderStatus.CANCELLED)


@router.put("/{order_id}/status", response_model=OrderOut)
async def update_order_status_route(
    order_id: int,
    status_in: OrderUpdateStatus,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: Annotated[User, Depends(get_admin_user)],
) -> Any:
    """
    Update order status. Admins only.
    """
    order = await get_order_by_id(db, order_id=order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return await update_order_status(db, order=order, new_status=status_in.status)


@router.post(
    "/{order_id}/returns",
    response_model=OrderReturnOut,
    status_code=status.HTTP_201_CREATED,
)
async def request_item_return(
    order_id: int,
    return_in: OrderReturnCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Submit a return request for an item in a delivered order.
    """
    order = await get_order_by_id(db, order_id=order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    if order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to return items for this order",
        )
    try:
        return await create_order_return(
            db, order=order, user_id=current_user.id, return_in=return_in
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None


@router.get("/{order_id}/returns", response_model=list[OrderReturnOut])
async def list_order_returns(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Get all returns submitted for a specific order.
    """
    order = await get_order_by_id(db, order_id=order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    if order.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view returns for this order",
        )
    return order.returns
