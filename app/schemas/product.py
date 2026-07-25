from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Brand Schemas
class BrandBase(BaseModel):
    name: str
    slug: str
    logo_url: str | None = None


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    logo_url: str | None = None


class BrandOut(BrandBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Category Schemas
class CategoryBase(BaseModel):
    name: str
    slug: str
    parent_id: int | None = None
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    parent_id: int | None = None
    is_active: bool | None = None


class CategoryOut(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Product Variant Schemas
class ProductVariantBase(BaseModel):
    sku: str
    name: str
    price: float
    quantity_in_stock: int = 0
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantUpdate(BaseModel):
    sku: str | None = None
    name: str | None = None
    price: float | None = None
    quantity_in_stock: int | None = None
    attributes: dict[str, Any] | None = None


class ProductVariantOut(ProductVariantBase):
    id: int
    product_id: int

    model_config = ConfigDict(from_attributes=True)


# Review Schemas
class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    title: str | None = None
    content: str | None = None
    verified_purchase: bool = False
    is_active: bool = True


class ReviewCreate(ReviewBase):
    pass


class ReviewOut(ReviewBase):
    id: int
    product_id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Product Schemas
class ProductBase(BaseModel):
    sku: str
    name: str
    slug: str
    price: float
    category_id: int
    brand_id: int
    quantity_in_stock: int = 0
    images: list[str] = Field(default_factory=list)
    is_active: bool = True
    is_featured: bool = False
    seo_title: str | None = None
    seo_keywords: str | None = None


class ProductCreate(ProductBase):
    variants: list[ProductVariantCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    sku: str | None = None
    name: str | None = None
    slug: str | None = None
    price: float | None = None
    category_id: int | None = None
    brand_id: int | None = None
    quantity_in_stock: int | None = None
    images: list[str] | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    seo_title: str | None = None
    seo_keywords: str | None = None


class ProductOut(ProductBase):
    id: int
    rating: float
    review_count: int
    created_at: datetime
    category: CategoryOut
    brand: BrandOut
    variants: list[ProductVariantOut] = []

    model_config = ConfigDict(from_attributes=True)
