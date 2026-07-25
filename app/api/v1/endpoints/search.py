from typing import Any

from fastapi import APIRouter, Query

from app.schemas.search import SearchResponse
from app.services.elasticsearch_service import ElasticsearchService

router = APIRouter()


@router.get("/", response_model=SearchResponse)
def search_products(
    q: str | None = Query(None, description="Search search query"),
    category: str | None = Query(None, description="Filter by category name"),
    brand: str | None = Query(None, description="Filter by brand name"),
    min_price: float | None = Query(None, description="Minimum price filter"),
    max_price: float | None = Query(None, description="Maximum price filter"),
    sort: str
    | None = Query(None, description="Sort field (price_asc, price_desc, rating)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> Any:
    """
    Search products using Elasticsearch.
    """
    return ElasticsearchService.search_products(
        query=q or "",
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort,
        skip=skip,
        limit=limit,
    )


@router.get("/autocomplete", response_model=list[str])
def autocomplete(
    q: str = Query(..., min_length=1, description="Prefix match query string")
) -> Any:
    """
    Retrieve auto-complete search suggestions.
    """
    return ElasticsearchService.autocomplete(query=q)
