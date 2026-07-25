from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user
from app.core.cache import cached, invalidate_cache
from app.crud.product import create_category, get_categories, get_category_by_slug
from app.db.base import get_db
from app.models.user import User
from app.schemas.product import CategoryCreate, CategoryOut

router = APIRouter()


@router.get("/", response_model=list[CategoryOut])
@cached(prefix="categories:list")
async def list_categories(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    List all categories.
    """
    return await get_categories(db, skip=skip, limit=limit)


@router.get("/{slug}", response_model=CategoryOut)
async def read_category_by_slug(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Get a category by its slug.
    """
    category = await get_category_by_slug(db, slug=slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


@router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_new_category(
    category_in: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: Annotated[User, Depends(get_admin_user)],
) -> Any:
    """
    Create a new category. Admins only.
    """
    existing = await get_category_by_slug(db, slug=category_in.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this slug already exists",
        )
    category = await create_category(db, obj_in=category_in)
    invalidate_cache("categories:list:*")
    return category
