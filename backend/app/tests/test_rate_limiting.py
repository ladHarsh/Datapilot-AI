import pytest
import time
from fastapi import FastAPI, Request
from starlette.testclient import TestClient
from app.middleware.rate_limit_middleware import RateLimitMiddleware

def test_rate_limiting_enforcement():
    app = FastAPI()
    # Lower limit for testing
    class TestRateLimitMiddleware(RateLimitMiddleware):
        RATE_LIMIT = 5
        WINDOW_SECONDS = 1
        
    app.add_middleware(TestRateLimitMiddleware)

    @app.get("/")
    async def root():
        return {"ok": True}

    client = TestClient(app)
    
    # 1. First 5 requests should pass
    for _ in range(5):
        response = client.get("/")
        assert response.status_code == 200
        
    # 2. 6th request should fail
    response = client.get("/")
    assert response.status_code == 429
    assert response.json()["detail"] == "Too many requests. Please try again later."
    
    # 3. Wait for window to reset
    time.sleep(1.1)
    response = client.get("/")
    assert response.status_code == 200
