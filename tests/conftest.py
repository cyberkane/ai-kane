# -*- coding: utf-8 -*-
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from main import app, app_config

@pytest.fixture(scope="function")  # FIXED: Changed back to standard scope
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an isolated, in-memory AsyncClient connected natively 
    to the FastAPI ASGI layer without requiring Uvicorn overhead.
    """
    if "chat" not in app_config:
        app_config["chat"] = {"host": "http://localhost", "port": "11434", "model": "llama3.1:8b"}
    if "vault" not in app_config:
        app_config["vault"] = {"host": "http://localhost", "port": "8200", "token": "mock_token"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
