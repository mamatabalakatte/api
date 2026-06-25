import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.models import Base
from app.database.repository import UserRepository, ContentRepository, InteractionRepository, SkillRepository

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

def test_create_skill(db):
    skill = SkillRepository.get_or_create(db, "Python")
    assert skill.name == "Python"
    
    skill2 = SkillRepository.get_or_create(db, "Python")
    assert skill2.id == skill.id
    assert len(SkillRepository.list_all(db)) == 1

def test_create_user(db):
    user = UserRepository.create(db, "test_user", ["Python", "FastAPI"])
    assert user.username == "test_user"
    assert len(user.skills) == 2
    assert {s.name for s in user.skills} == {"Python", "FastAPI"}
    
    fetched = UserRepository.get_by_id(db, user.id)
    assert fetched.username == "test_user"
    
    by_name = UserRepository.get_by_username(db, "test_user")
    assert by_name.id == user.id
    
    assert len(UserRepository.list_all(db)) == 1

def test_create_content(db):
    content = ContentRepository.create(db, "ML Intro", "course", "Learn ML", ["Python", "Machine Learning"])
    assert content.title == "ML Intro"
    assert content.type == "course"
    assert len(content.skills) == 2
    
    fetched = ContentRepository.get_by_id(db, content.id)
    assert fetched.title == "ML Intro"
    assert len(ContentRepository.list_all(db)) == 1

def test_create_interaction(db):
    user = UserRepository.create(db, "alice")
    content = ContentRepository.create(db, "ML Intro", "course", "Learn ML")
    
    interaction = InteractionRepository.create(db, user.id, content.id, "like", 5.0)
    assert interaction.user_id == user.id
    assert interaction.content_id == content.id
    assert interaction.interaction_type == "like"
    assert interaction.rating == 5.0

    inters = InteractionRepository.get_by_user_id(db, user.id)
    assert len(inters) == 1
    assert inters[0].id == interaction.id
    
    assert len(InteractionRepository.list_all(db)) == 1
