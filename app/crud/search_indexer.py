from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.services.elasticsearch_service import ElasticsearchService


async def update_product_index(db: AsyncSession, product_id: int) -> None:
    """
    Eagerly load the product details and index it in Elasticsearch.
    If the product has been soft-deleted, remove it from the index.
    """
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        # If product does not exist, delete from index
        ElasticsearchService.delete_product(product_id)
        return

    if product.deleted_at is not None:
        ElasticsearchService.delete_product(product_id)
    else:
        ElasticsearchService.index_product(
            product_id=product.id,
            name=product.name,
            description=None,
            sku=product.sku,
            category_name=product.category.name if product.category else None,
            brand_name=product.brand.name if product.brand else None,
            price=product.price,
            rating=product.rating,
        )
