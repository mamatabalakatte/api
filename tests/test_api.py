import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import get_db, Base
from app.api.main import app
from app.database.repository import UserRepository, ContentRepository, InteractionRepository

DB_FILE = "test_api_recommendations.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(name="client", scope="module")
def client_fixture():
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            pass
            
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    UserRepository.create(db, "alice", ["Python"])
    ContentRepository.create(db, "FastAPI Tutorial", "tutorial", skill_names=["Python"])
    db.close()
    
    with TestClient(app) as client:
        yield client
        
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            pass

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["database_connected"] is True

def test_get_recommendations(client):
    # alice is user 1
    response = client.get("/recommendations?user_id=1&n=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["content"]["title"] == "FastAPI Tutorial"

def test_get_recommendations_not_found(client):
    response = client.get("/recommendations?user_id=999")
    assert response.status_code == 404
    assert "not exist" in response.json()["detail"]

def test_submit_feedback(client):
    payload = {
        "user_id": 1,
        "content_id": 1,
        "interaction_type": "like",
        "rating": 5.0
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_submit_feedback_invalid(client):
    payload = {
        "user_id": 1,
        "content_id": 1,
        "interaction_type": "dislike",
        "rating": 5.0
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 422

def test_metrics(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "precision_at_5" in data
    assert "recall_at_5" in data
    assert "ndcg_at_5" in data
    assert data["total_users"] == 1
    assert data["total_contents"] == 1
