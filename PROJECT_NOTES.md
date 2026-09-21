# Project Recall — Apex Commerce

## One-line explanation
FastAPI e-commerce backend/storefront with products, variants, carts, orders, tracking, JWT auth and async database access.

## Main technical pieces
- FastAPI
- Async SQLAlchemy
- PostgreSQL / SQLite
- JWT authentication
- Redis/Celery
- Docker
- Pytest

## Security reminders
- Never commit a real .env file.
- Never reuse seeded admin passwords on a live deployment.
- Rotate any secret that has ever been exposed publicly.
- Keep local databases out of Git.

## Interview questions
1. Why use async database access?
2. How is JWT authentication validated?
3. How would you prevent overselling stock?
4. Where should order-state transitions be validated?
5. Which operations should run in background workers?

## Next improvements
- Restricted demo account
- CI status
- Screenshots
- Deployment hardening
