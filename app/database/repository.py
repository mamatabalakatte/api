from sqlalchemy.orm import Session
from app.database.models import User, Content, Skill, Interaction
from typing import List, Optional

class SkillRepository:
    @staticmethod
    def get_by_id(db: Session, skill_id: int) -> Optional[Skill]:
        return db.query(Skill).filter(Skill.id == skill_id).first()

    @staticmethod
    def get_by_name(db: Session, name: str) -> Optional[Skill]:
        return db.query(Skill).filter(Skill.name == name).first()

    @staticmethod
    def get_or_create(db: Session, name: str) -> Skill:
        name_clean = name.strip()
        skill = SkillRepository.get_by_name(db, name_clean)
        if not skill:
            skill = Skill(name=name_clean)
            db.add(skill)
            db.commit()
            db.refresh(skill)
        return skill

    @staticmethod
    def list_all(db: Session) -> List[Skill]:
        return db.query(Skill).all()

class UserRepository:
    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def create(db: Session, username: str, skill_names: List[str] = None) -> User:
        user = User(username=username)
        db.add(user)
        if skill_names:
            for skill_name in skill_names:
                skill = SkillRepository.get_or_create(db, skill_name)
                user.skills.append(skill)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def list_all(db: Session) -> List[User]:
        return db.query(User).all()

class ContentRepository:
    @staticmethod
    def get_by_id(db: Session, content_id: int) -> Optional[Content]:
        return db.query(Content).filter(Content.id == content_id).first()

    @staticmethod
    def create(db: Session, title: str, content_type: str, description: str = None, skill_names: List[str] = None) -> Content:
        content = Content(title=title, type=content_type, description=description)
        db.add(content)
        if skill_names:
            for skill_name in skill_names:
                skill = SkillRepository.get_or_create(db, skill_name)
                content.skills.append(skill)
        db.commit()
        db.refresh(content)
        return content

    @staticmethod
    def list_all(db: Session) -> List[Content]:
        return db.query(Content).all()

class InteractionRepository:
    @staticmethod
    def create(db: Session, user_id: int, content_id: int, interaction_type: str, rating: Optional[float] = None) -> Interaction:
        interaction = Interaction(
            user_id=user_id,
            content_id=content_id,
            interaction_type=interaction_type,
            rating=rating
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        return interaction

    @staticmethod
    def get_by_user_id(db: Session, user_id: int) -> List[Interaction]:
        return db.query(Interaction).filter(Interaction.user_id == user_id).all()

    @staticmethod
    def list_all(db: Session) -> List[Interaction]:
        return db.query(Interaction).all()
