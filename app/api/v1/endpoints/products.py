from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user, get_current_user
from app.core.cache import cached, invalidate_cache
from app.crud.product import (
    create_product,
    create_review,
    delete_product,
    get_product_by_id,
    get_product_reviews,
    get_products,
    update_product,
)
from app.db.base import get_db
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductOut,
    ProductUpdate,
    ReviewCreate,
    ReviewOut,
)

router = APIRouter()


@router.get("/", response_model=list[ProductOut])
@cached(prefix="products:list")
async def list_products(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
    sort_by: str | None = None,
    category_id: int | None = None,
    brand_id: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    search: str | None = None,
) -> list[Any]:  # Using Any to avoid type checking issues with SQLAlchemy models
    """
    Retrieve products with pagination, sorting, search, and filtering.
    """
    # Wait, mypy might complain about returning list[Product] for
    # list[ProductOut] due to models. We can cast or specify the type.
    # Let's just return what get_products yields.
    products = await get_products(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        category_id=category_id,
        brand_id=brand_id,
        price_min=price_min,
        price_max=price_max,
        search=search,
    )
    return products


@router.get("/{product_id}", response_model=ProductOut)
@cached(prefix="products:detail")
async def read_product(
    product_id: int,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Get product by ID.
    """
    product = await get_product_by_id(db, product_id=product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


@router.post("/", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_new_product(
    product_in: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: Annotated[User, Depends(get_admin_user)],
) -> Any:
    """
    Create a new product. Admins only.
    """
    prod = await create_product(db, obj_in=product_in)
    invalidate_cache("products:list:*")
    return prod


@router.put("/{product_id}", response_model=ProductOut)
async def update_existing_product(
    product_id: int,
    product_in: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: Annotated[User, Depends(get_admin_user)],
) -> Any:
    """
    Update a product. Admins only.
    """
    product = await get_product_by_id(db, product_id=product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    prod = await update_product(db, db_obj=product, obj_in=product_in)
    invalidate_cache("products:list:*")
    invalidate_cache(f"products:detail:{product_id}")
    return prod


@router.delete("/{product_id}", response_model=ProductOut)
async def delete_existing_product(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: Annotated[User, Depends(get_admin_user)],
) -> Any:
    """
    Soft delete a product. Admins only.
    """
    product = await get_product_by_id(db, product_id=product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    prod = await delete_product(db, db_obj=product)
    invalidate_cache("products:list:*")
    invalidate_cache(f"products:detail:{product_id}")
    return prod


# Product Reviews
@router.post(
    "/{product_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_review(
    product_id: int,
    review_in: ReviewCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Create a review for a product. Authenticated users only.
    """
    product = await get_product_by_id(db, product_id=product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    rev = await create_review(
        db, product_id=product_id, user_id=current_user.id, obj_in=review_in
    )
    invalidate_cache("products:list:*")
    invalidate_cache(f"products:detail:{product_id}")
    return rev


@router.get("/{product_id}/reviews", response_model=list[ReviewOut])
async def list_product_reviews(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Get active reviews for a product.
    """
    product = await get_product_by_id(db, product_id=product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return await get_product_reviews(db, product_id=product_id, skip=skip, limit=limit)
