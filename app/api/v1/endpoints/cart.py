from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.crud.cart import (
    add_item_to_cart,
    clear_cart,
    get_user_cart,
    remove_item_from_cart,
)
from app.db.base import get_db
from app.models.user import User
from app.schemas.cart import CartItemBase, CartItemOut, CartOut

router = APIRouter()


@router.get("/", response_model=CartOut)
async def view_cart(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Retrieve current active user's shopping cart.
    """
    return await get_user_cart(db, user_id=current_user.id)


@router.post("/add", response_model=CartItemOut, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    item_in: CartItemBase,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Add a product variant to the current user's cart.
    """
    try:
        return await add_item_to_cart(db, user_id=current_user.id, item_in=item_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None


@router.delete("/{item_id}", status_code=status.HTTP_200_OK)
async def delete_cart_item(
    item_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """
    Remove an item from the current user's cart.
    """
    success = await remove_item_from_cart(db, user_id=current_user.id, item_id=item_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )
    return {"message": "Item removed from cart"}


@router.post("/clear", status_code=status.HTTP_200_OK)
async def clear_user_cart(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """
    Clear all items in the current user's cart.
    """
    await clear_cart(db, user_id=current_user.id)
    return {"message": "Cart cleared"}
