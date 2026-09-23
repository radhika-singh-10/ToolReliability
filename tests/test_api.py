from fastapi.testclient import TestClient
from toolreliability.api import app


client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "healthy"}


def test_run_suite():
    response = client.post("/api/runs?agent=reference")
    assert response.status_code == 200
    assert response.json()["pass_rate"] == 1.0

