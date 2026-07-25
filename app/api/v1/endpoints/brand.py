from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user
from app.core.cache import cached, invalidate_cache
from app.crud.product import create_brand, get_brand_by_slug, get_brands
from app.db.base import get_db
from app.models.user import User
from app.schemas.product import BrandCreate, BrandOut

router = APIRouter()


@router.get("/", response_model=list[BrandOut])
@cached(prefix="brands:list")
async def list_brands(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    List all brands.
    """
    return await get_brands(db, skip=skip, limit=limit)


@router.post("/", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
async def create_new_brand(
    brand_in: BrandCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: Annotated[User, Depends(get_admin_user)],
) -> Any:
    """
    Create a new brand. Admins only.
    """
    existing = await get_brand_by_slug(db, slug=brand_in.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brand with this slug already exists",
        )
    brand = await create_brand(db, obj_in=brand_in)
    invalidate_cache("brands:list:*")
    return brand
