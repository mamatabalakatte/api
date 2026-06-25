import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.models import Base
from app.database.repository import UserRepository, ContentRepository, InteractionRepository
from app.engine.recommender import RecommenderEngine
from app.utils.evaluation import precision_at_k, recall_at_k, ndcg_at_k, evaluate_system

DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db")
def db_fixture():
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

def test_precision_at_k():
    assert precision_at_k([1, 2, 3], {2, 4}, 3) == 1/3
    assert precision_at_k([1, 2, 3], {2, 4}, 2) == 0.5
    assert precision_at_k([], {1}, 5) == 0.0
    assert precision_at_k([1], set(), 5) == 0.0
    assert precision_at_k([1], {1}, 0) == 0.0

def test_recall_at_k():
    assert recall_at_k([1, 2, 3], {2, 4}, 3) == 0.5
    assert recall_at_k([1, 2, 3], {2, 4}, 1) == 0.0
    assert recall_at_k([], {1}, 5) == 0.0
    assert recall_at_k([1], set(), 5) == 0.0

def test_ndcg_at_k():
    # Recommended [1, 2, 3], Relevant {2, 3}
    # DCG = rel_1 / log2(2) + rel_2 / log2(3) + rel_3 / log2(4)
    # rel_1 = 0 (1 is not in actual)
    # rel_2 = 1 (2 is in actual)
    # rel_3 = 1 (3 is in actual)
    # DCG = 0 + 1/log2(3) + 1/log2(4) = 0.6309 + 0.5 = 1.1309
    # IDCG = 1/log2(2) + 1/log2(3) = 1 + 0.6309 = 1.6309
    # NDCG = 1.1309 / 1.6309 = ~0.6934
    val = ndcg_at_k([1, 2, 3], {2, 3}, 3)
    assert abs(val - 0.6934) < 1e-3

    assert ndcg_at_k([], {1}, 5) == 0.0
    assert ndcg_at_k([1], set(), 5) == 0.0
    assert ndcg_at_k([1], {1}, 0) == 0.0

def test_evaluate_system_insufficient_data(db):
    recommender = RecommenderEngine()
    res = evaluate_system(db, recommender)
    assert res["precision_at_k"] == 0.0
    assert "Insufficient" in res["status"]

def test_evaluate_system_success(db):
    recommender = RecommenderEngine()
    
    # Create contents
    contents = [ContentRepository.create(db, f"C{i}", "tutorial") for i in range(10)]
    
    # Create users with interests
    u1 = UserRepository.create(db, "u1", ["Python"])
    u2 = UserRepository.create(db, "u2", ["Python"])
    
    # Add multiple interactions per user to allow 80/20 train/test split
    # User 1 has 5 interactions
    for i in range(5):
        InteractionRepository.create(db, u1.id, contents[i].id, "like")
    # User 2 has 5 interactions
    for i in range(5):
        InteractionRepository.create(db, u2.id, contents[i+5].id, "like")
        
    res = evaluate_system(db, recommender, k=2)
    assert res["status"] == "Success"
    assert res["evaluated_users"] > 0
    assert "precision_at_k" in res
    assert "recall_at_5" not in res # because we ran with k=2, so it returns "precision_at_k" etc.
