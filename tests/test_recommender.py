import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.models import Base
from app.database.repository import UserRepository, ContentRepository, InteractionRepository
from app.engine.recommender import RecommenderEngine

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

def test_recommender_cold_start_popularity(db):
    recommender = RecommenderEngine()
    
    c1 = ContentRepository.create(db, "Content 1", "tutorial")
    c2 = ContentRepository.create(db, "Content 2", "tutorial")
    c3 = ContentRepository.create(db, "Content 3", "tutorial")
    
    u1 = UserRepository.create(db, "user1")
    u2 = UserRepository.create(db, "user2")
    u3 = UserRepository.create(db, "cold_user")  # no skills, no interactions
    
    InteractionRepository.create(db, u1.id, c1.id, "like")
    InteractionRepository.create(db, u2.id, c1.id, "click")
    InteractionRepository.create(db, u2.id, c2.id, "bookmark")
    
    recs = recommender.get_recommendations(db, u3.id, n=2)
    assert len(recs) == 2
    assert recs[0]["content"]["id"] == c1.id
    assert recs[0]["method"] == "Popularity-Based"

def test_recommender_cold_start_skills(db):
    recommender = RecommenderEngine()
    
    c1 = ContentRepository.create(db, "FastAPI Tutorial", "tutorial", skill_names=["FastAPI", "Python"])
    c2 = ContentRepository.create(db, "React Tutorial", "tutorial", skill_names=["React", "JavaScript"])
    
    u1 = UserRepository.create(db, "pythonist", skill_names=["Python", "FastAPI"])
    
    recs = recommender.get_recommendations(db, u1.id, n=1)
    assert len(recs) == 1
    assert recs[0]["content"]["id"] == c1.id
    assert recs[0]["method"] == "Content-Based (Skills Overlap)"

def test_recommender_caching(db):
    recommender = RecommenderEngine()
    
    c1 = ContentRepository.create(db, "Content 1", "tutorial")
    u1 = UserRepository.create(db, "user1", ["Python"])
    
    recs1 = recommender.get_recommendations(db, u1.id, n=1)
    assert len(recs1) == 1
    assert recs1[0]["cached"] is False
    
    recs2 = recommender.get_recommendations(db, u1.id, n=1)
    assert len(recs2) == 1
    assert recs2[0]["cached"] is True
    
    recommender.invalidate_cache(u1.id)
    recs3 = recommender.get_recommendations(db, u1.id, n=1)
    assert recs3[0]["cached"] is False

def test_recommender_hybrid_warm_user(db):
    recommender = RecommenderEngine()
    
    # Create contents
    c1 = ContentRepository.create(db, "Python Basics", "tutorial", skill_names=["Python"])
    c2 = ContentRepository.create(db, "FastAPI Deep Dive", "course", skill_names=["FastAPI", "Python"])
    c3 = ContentRepository.create(db, "React Introduction", "course", skill_names=["React"])
    
    # Create users
    u1 = UserRepository.create(db, "user1", ["Python", "FastAPI"])
    u2 = UserRepository.create(db, "user2", ["Python"])
    
    # Interacted contents (warm user setup)
    InteractionRepository.create(db, u1.id, c1.id, "complete")
    InteractionRepository.create(db, u2.id, c1.id, "complete")
    InteractionRepository.create(db, u2.id, c2.id, "like", 5.0)
    
    # Now recommend for u1. u1 has interacted with c1. They should be recommended c2 due to skill overlap and u2's similarity.
    recs = recommender.get_recommendations(db, u1.id, n=2)
    
    assert len(recs) >= 1
    # The first recommendation should be Content 2 (FastAPI Deep Dive)
    assert recs[0]["content"]["id"] == c2.id
    assert recs[0]["method"] in ["Hybrid (Collaborative + Content-Based)", "Collaborative Filtering", "Content-Based (Skills)"]

