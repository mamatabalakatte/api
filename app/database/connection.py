import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from app.database.models import Base

# Support custom DB path, defaulting to recommendations.db in workspace
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///recommendations.db")

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Needed for SQLite in multithreaded environment (like FastAPI)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)

def init_db():
    """Initializes the database, creating all tables."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for obtaining database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
