from pydantic import BaseModel


class SearchResultItem(BaseModel):
    id: int
    name: str
    description: str
    sku: str
    category_name: str
    brand_name: str
    price: float
    rating: float


class SearchFacets(BaseModel):
    categories: dict[str, int]
    brands: dict[str, int]


class SearchResponse(BaseModel):
    total: int
    results: list[SearchResultItem]
    facets: SearchFacets
