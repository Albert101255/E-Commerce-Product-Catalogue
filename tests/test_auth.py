import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "password": "securepassword"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert data["role"] == UserRole.CUSTOMER


@pytest.mark.asyncio
async def test_register_existing_user(client: AsyncClient, db: AsyncSession) -> None:
    # First create user
    user = User(
        email="existing@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    await db.flush()

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "existing@example.com", "password": "securepassword"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "The user with this email already exists in the system."
    )


@pytest.mark.asyncio
async def test_login_user(client: AsyncClient, db: AsyncSession) -> None:
    user = User(
        email="login@example.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    await db.flush()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_incorrect_password(client: AsyncClient, db: AsyncSession) -> None:
    user = User(
        email="wrongpass@example.com",
        hashed_password=get_password_hash("correctpass"),
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    await db.flush()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403  # HTTPBearer returns 403 if header is missing


@pytest.mark.asyncio
async def test_get_me_authorized(client: AsyncClient, db: AsyncSession) -> None:
    # Register and login to get token
    await client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_update_me(client: AsyncClient, db: AsyncSession) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "update@example.com", "password": "password123"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "update@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    response = await client.put(
        "/api/v1/auth/me",
        json={"email": "updated@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "updated@example.com"


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, db: AsyncSession) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "changepass@example.com", "password": "oldpassword"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepass@example.com", "password": "oldpassword"},
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "oldpassword", "new_password": "newpassword"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"

    # Test login with new password
    login_new = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepass@example.com", "password": "newpassword"},
    )
    assert login_new.status_code == 200


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, db: AsyncSession) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@example.com", "password": "password123"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "password123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
