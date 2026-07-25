# ⚡ Apex Commerce — Enterprise E-Commerce Product Catalogue & Platform

An asynchronous, scalable e-commerce REST API and interactive storefront built with **Python 3.11+**, **FastAPI**, **SQLAlchemy 2.0**, **SQLite / PostgreSQL**, **Redis**, and **Celery**.

---

## 🌟 Key Features

* **⚡ Modern Fast Storefront UI:** Clean, responsive dark-mode e-commerce web application with real-time stock counters, variant selectors, and quantity calculators.
* **🛍️ Product & Catalog Management:** Flexible product schemas with dynamic variants (color, size, RAM), categories, brands, and real-time inventory tracking.
* **🚚 Real-Time Order Tracking:** Dedicated package tracking page (`/tracking`) with a 5-stage shipment visual progress timeline and carrier status telemetry.
* **🔒 Address Validation Enforcement:** Required shipping address fields validation prior to order placement.
* **🔑 Authentication & RBAC:** JWT authentication with Customer and Administrator role-based access control.
* **⚡ Async Architecture:** Powered by SQLAlchemy 2.0 Async Session, Uvicorn, and high-concurrency event loops.
* **⚙️ Background Workers:** Celery integration for async email dispatch, search indexing, and automated cart expiration.

---

## 📂 Architecture & Directory Structure

```text
.
├── app/
│   ├── api/
│   │   ├── dependencies.py       # Auth & DB Injection dependencies
│   │   └── v1/
│   │       ├── api.py            # API Router aggregator
│   │       └── endpoints/        # Endpoint routes (auth, products, cart, orders, etc.)
│   ├── core/                     # Security, config, cache, and rate limiting
│   ├── crud/                     # SQLAlchemy Async database query functions
│   ├── db/                       # Base Declarative schema & async engine session maker
│   ├── models/                   # SQLAlchemy Models (User, Product, Cart, Order, Payment)
│   ├── schemas/                  # Pydantic validation schemas
│   └── tasks/                    # Celery background tasks
├── static/                       # Frontend web app assets
│   ├── index.html                # Home storefront page
│   ├── products.html             # Dedicated product catalog page
│   ├── orders.html               # Customer orders list page
│   ├── tracking.html             # Real-time order tracking page
│   ├── shared.js                 # Global navigation & API client
│   ├── index.css                 # Core CSS design system
│   └── pages.css                 # Component & layout styles
├── tests/                        # Full Pytest test suite (100% passing)
├── pyproject.toml                # Poetry dependencies and package configuration
├── dev.db                        # Development SQLite database
└── README.md                     # Documentation
```

---

## 🚀 Quick Start Guide

### Prerequisites
* **Python 3.11+** installed
* **Poetry** or **Virtualenv**

### 1. Clone & Setup
```bash
git clone https://github.com/Albert101255/E-Commerce-Product-Catalogue.git
cd E-Commerce-Product-Catalogue

# Activate environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # or poetry install
```

### 2. Initialize Database & Run Server
```bash
# Set SQLite database URI and start server
export SQLALCHEMY_DATABASE_URI="sqlite+aiosqlite:///dev.db"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open in Browser
Once the server is running locally, access the web application routes:

| Route Name | Target URL | Description |
| :--- | :--- | :--- |
| **Storefront Home** | [`http://localhost:8000/`](http://localhost:8000/) | Main landing page & featured catalog |
| **Products Catalog** | [`http://localhost:8000/products`](http://localhost:8000/products) | Dedicated product list with filters & variants |
| **My Orders** | [`http://localhost:8000/orders`](http://localhost:8000/orders) | User purchase history & order details |
| **Order Tracking** | [`http://localhost:8000/tracking`](http://localhost:8000/tracking) | Real-time package tracking telemetry |

---

## 🔑 Default Credentials

### Administrator Account
* **Email:** `admin@store.com`
* **Password:** `AdminPass123!`

---

## 🧪 Running Tests

Execute the complete asynchronous test suite using `pytest`:

```bash
pytest
```

Output:
```text
===================== 29 passed in 21.74s =====================
```

---

## 🛠️ API Specifications

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register new user account | No |
| `POST` | `/api/v1/auth/login` | Authenticate and obtain JWT token | No |
| `GET` | `/api/v1/products/` | List products with pagination & search | No |
| `GET` | `/api/v1/products/{id}` | Get detailed product by ID | No |
| `POST` | `/api/v1/cart/add` | Add product variant to cart | Yes |
| `GET` | `/api/v1/cart/` | Retrieve active shopping cart | Yes |
| `POST` | `/api/v1/orders/` | Place a new order | Yes |
| `GET` | `/api/v1/orders/` | List customer orders | Yes |
| `GET` | `/api/v1/orders/{id}` | Retrieve order status & tracking details | Yes |

---

## 📝 License
This project is licensed under the MIT License.
