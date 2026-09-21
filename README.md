# Apex Commerce — E-Commerce Product Catalogue

A FastAPI-based e-commerce backend and storefront with asynchronous SQLAlchemy, JWT authentication, product variants, carts, orders, tracking, Redis/Celery support, and Docker-based deployment.

## What this project demonstrates

- Python 3.11+ and FastAPI API design
- Async SQLAlchemy 2.0 database access
- JWT authentication and role-based authorization
- Product/catalog, cart, order, and tracking workflows
- Background task integration with Celery
- Redis-backed infrastructure
- Pytest-based automated testing
- Local and containerized development

## Features

- Product catalogue with categories, brands, variants, stock and search
- Customer registration/login
- Shopping cart and order creation
- Order history and shipment-status tracking
- Admin/customer role separation
- Address validation before checkout
- Background worker integration for asynchronous jobs

## Architecture

```text
Client / Storefront
        |
        v
FastAPI API
        |
  +-----+------+
  |            |
SQLAlchemy   Celery
  |            |
PostgreSQL   Redis
```

The code is organized into API routes, dependencies, schemas, models, CRUD logic, services and background tasks under `app/`.

## Local setup

### Requirements

- Python 3.11+
- PostgreSQL or SQLite
- Redis if running worker-backed features

### Run locally

```bash
git clone https://github.com/Albert101255/E-Commerce-Product-Catalogue.git
cd E-Commerce-Product-Catalogue

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Replace all placeholder credentials/secrets before use.

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testing

```bash
pytest
```

The repository contains an automated Pytest suite. Test counts and coverage can change as the project evolves, so the current test run should be treated as the source of truth rather than a hard-coded metric in this README.

## Live demo

A deployment has been configured at:

- https://e-commerce-product-catalogue.onrender.com/

Do not reuse local seed/admin credentials on an internet-facing deployment. Public demos should use restricted demo accounts and rotated secrets.

## Security notes

- Real `.env` files are ignored and should never be committed.
- `.env.example` contains placeholders only.
- Local database files are ignored.
- Production deployments should use strong generated secrets, managed credentials, HTTPS, migrations and backups.

## API examples

Typical routes include:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/products/`
- `POST /api/v1/cart/add`
- `GET /api/v1/cart/`
- `POST /api/v1/orders/`
- `GET /api/v1/orders/`
- `GET /api/v1/orders/{id}`

## Current focus

This repository is a learning and portfolio project. The strongest next improvements are deployment hardening, a restricted public demo account, screenshots, CI visibility, and more explicit performance/coverage measurement.

## Licensing

No repository license file is currently included. Add one deliberately if you want to grant reuse rights.
