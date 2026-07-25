from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    brand,
    cart,
    category,
    orders,
    payments,
    products,
    search,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(category.router, prefix="/category", tags=["category"])
api_router.include_router(brand.router, prefix="/brand", tags=["brand"])
api_router.include_router(cart.router, prefix="/cart", tags=["cart"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(payments.router, tags=["payments"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
