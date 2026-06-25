from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# Many-to-many association table for User and Skill
user_skills = Table(
    "user_skills",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many association table for Content and Skill
content_skills = Table(
    "content_skills",
    Base.metadata,
    Column("content_id", Integer, ForeignKey("content.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    
    # Relationships
    skills = relationship("Skill", secondary=user_skills, back_populates="users")
    interactions = relationship("Interaction", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "skills": [skill.name for skill in self.skills]
        }

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    # Relationships
    users = relationship("User", secondary=user_skills, back_populates="skills")
    contents = relationship("Content", secondary=content_skills, back_populates="skills")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name
        }

class Content(Base):
    __tablename__ = "content"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    type = Column(String, nullable=False)  # e.g., "tutorial", "project", "course"
    description = Column(String, nullable=True)

    # Relationships
    skills = relationship("Skill", secondary=content_skills, back_populates="contents")
    interactions = relationship("Interaction", back_populates="content", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "description": self.description,
            "skills": [skill.name for skill in self.skills]
        }

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(Integer, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    interaction_type = Column(String, nullable=False)  # e.g., "click", "bookmark", "like", "complete"
    rating = Column(Float, nullable=True)  # optional rating
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="interactions")
    content = relationship("Content", back_populates="interactions")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content_id": self.content_id,
            "interaction_type": self.interaction_type,
            "rating": self.rating,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
