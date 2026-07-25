from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Brand, Category, Product, ProductVariant, Review
from app.schemas.product import (
    BrandCreate,
    CategoryCreate,
    ProductCreate,
    ProductUpdate,
    ReviewCreate,
)


# Category CRUD
async def get_category_by_id(db: AsyncSession, category_id: int) -> Category | None:
    result = await db.execute(select(Category).where(Category.id == category_id))
    return result.scalar_one_or_none()


async def get_category_by_slug(db: AsyncSession, slug: str) -> Category | None:
    result = await db.execute(select(Category).where(Category.slug == slug))
    return result.scalar_one_or_none()


async def create_category(db: AsyncSession, obj_in: CategoryCreate) -> Category:
    db_obj = Category(**obj_in.model_dump())
    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)
    return db_obj


async def get_categories(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[Category]:
    result = await db.execute(select(Category).offset(skip).limit(limit))
    return list(result.scalars().all())


# Brand CRUD
async def get_brand_by_id(db: AsyncSession, brand_id: int) -> Brand | None:
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    return result.scalar_one_or_none()


async def get_brand_by_slug(db: AsyncSession, slug: str) -> Brand | None:
    result = await db.execute(select(Brand).where(Brand.slug == slug))
    return result.scalar_one_or_none()


async def create_brand(db: AsyncSession, obj_in: BrandCreate) -> Brand:
    db_obj = Brand(**obj_in.model_dump())
    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)
    return db_obj


async def get_brands(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Brand]:
    result = await db.execute(select(Brand).offset(skip).limit(limit))
    return list(result.scalars().all())


# Product CRUD
async def get_product_by_id(db: AsyncSession, product_id: int) -> Product | None:
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .where(Product.deleted_at.is_(None))
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.variants),
        )
    )
    return result.scalar_one_or_none()


async def get_product_by_slug(db: AsyncSession, slug: str) -> Product | None:
    result = await db.execute(
        select(Product)
        .where(Product.slug == slug)
        .where(Product.deleted_at.is_(None))
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.variants),
        )
    )
    return result.scalar_one_or_none()


async def create_product(db: AsyncSession, obj_in: ProductCreate) -> Product:
    product_data = obj_in.model_dump(exclude={"variants"})
    db_obj = Product(**product_data)
    db.add(db_obj)
    await db.flush()

    for variant_in in obj_in.variants:
        variant_obj = ProductVariant(**variant_in.model_dump(), product_id=db_obj.id)
        db.add(variant_obj)

    await db.flush()
    # Eagerly refresh and load relationships
    result = await db.execute(
        select(Product)
        .where(Product.id == db_obj.id)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.variants),
        )
    )
    product = result.scalar_one()
    from app.tasks.celery_tasks import async_update_product_search_index

    async_update_product_search_index.delay(product.id)
    return product


async def update_product(
    db: AsyncSession, db_obj: Product, obj_in: ProductUpdate
) -> Product:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)
    from app.tasks.celery_tasks import async_update_product_search_index

    async_update_product_search_index.delay(db_obj.id)
    return db_obj


async def delete_product(db: AsyncSession, db_obj: Product) -> Product:
    # Soft delete
    db_obj.deleted_at = datetime.now(UTC)
    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)
    from app.tasks.celery_tasks import async_update_product_search_index

    async_update_product_search_index.delay(db_obj.id)
    return db_obj


async def get_products(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    sort_by: str | None = None,
    category_id: int | None = None,
    brand_id: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    search: str | None = None,
) -> list[Product]:
    query = select(Product).where(Product.deleted_at.is_(None))

    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if brand_id is not None:
        query = query.where(Product.brand_id == brand_id)
    if price_min is not None:
        query = query.where(Product.price >= price_min)
    if price_max is not None:
        query = query.where(Product.price <= price_max)
    if search:
        query = query.where(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%"),
            )
        )

    # Sorting
    if sort_by == "price":
        query = query.order_by(Product.price.asc())
    elif sort_by == "-price":
        query = query.order_by(Product.price.desc())
    elif sort_by == "rating":
        query = query.order_by(Product.rating.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    query = (
        query.offset(skip)
        .limit(limit)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.variants),
        )
    )
    result = await db.execute(query)
    return list(result.scalars().all())


# Review CRUD & Denormalization
async def create_review(
    db: AsyncSession, product_id: int, user_id: int, obj_in: ReviewCreate
) -> Review:
    db_obj = Review(**obj_in.model_dump(), product_id=product_id, user_id=user_id)
    db.add(db_obj)
    await db.flush()

    # Recalculate average rating and review count
    result = await db.execute(
        select(func.coalesce(func.avg(Review.rating), 0.0), func.count(Review.id))
        .where(Review.product_id == product_id)
        .where(Review.is_active.is_(True))
    )
    avg_rating, count = result.all()[0]

    # Update product record
    product_result = await db.execute(select(Product).where(Product.id == product_id))
    product = product_result.scalar_one_or_none()
    if product:
        product.rating = float(avg_rating)
        product.review_count = int(count)
        db.add(product)

    await db.flush()
    await db.refresh(db_obj)
    from app.tasks.celery_tasks import async_update_product_search_index

    async_update_product_search_index.delay(product_id)
    return db_obj


async def get_product_reviews(
    db: AsyncSession, product_id: int, skip: int = 0, limit: int = 100
) -> list[Review]:
    result = await db.execute(
        select(Review)
        .where(Review.product_id == product_id)
        .where(Review.is_active.is_(True))
        .order_by(Review.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())
