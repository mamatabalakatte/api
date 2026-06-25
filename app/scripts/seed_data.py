import os
from sqlalchemy import text
from app.database.connection import SessionLocal, init_db, engine
from app.database.models import Base
from app.database.repository import UserRepository, ContentRepository, InteractionRepository, SkillRepository

def clear_db():
    """Drops and recreates all tables to ensure clean state."""
    # Close connection first if open
    Base.metadata.drop_all(bind=engine)
    init_db()

def seed():
    db = SessionLocal()
    try:
        print("Clearing database...")
        clear_db()
        print("Database tables initialized.")

        # Define Skills
        skills = [
            "Python", "SQL", "FastAPI", "Docker", "Machine Learning", 
            "Data Science", "React", "JavaScript", "Pandas", 
            "TensorFlow", "CSS", "HTML", "AWS"
        ]
        
        print("Creating skills...")
        for skill_name in skills:
            SkillRepository.get_or_create(db, skill_name)

        # Define Users with their initial skills
        users_data = [
            {"username": "alice", "skills": ["Python", "FastAPI", "SQL"]},
            {"username": "bob", "skills": ["React", "JavaScript", "CSS"]},
            {"username": "charlie", "skills": ["Machine Learning", "TensorFlow", "Pandas", "Python"]},
            {"username": "diana", "skills": ["AWS", "Docker", "SQL"]},
            {"username": "ethan", "skills": ["Python", "SQL"]},
            {"username": "fiona", "skills": ["React", "HTML", "CSS", "JavaScript"]},
            {"username": "george", "skills": ["Data Science", "Pandas", "Machine Learning"]},
            {"username": "hannah", "skills": ["Docker", "AWS"]},
            {"username": "ian", "skills": ["FastAPI", "Docker", "Python"]},
            {"username": "julia", "skills": ["Python", "Machine Learning"]},  # Cold-start user (no interactions)
            {"username": "kevin", "skills": ["React", "JavaScript"]},       # Cold-start user (no interactions)
            {"username": "leo", "skills": []}                               # Cold-start user (no skills, no interactions)
        ]

        print("Creating users...")
        users_map = {}
        for u in users_data:
            user = UserRepository.create(db, username=u["username"], skill_names=u["skills"])
            users_map[u["username"]] = user.id

        # Define Content items
        contents_data = [
            {"title": "FastAPI Crash Course", "type": "tutorial", "description": "Learn to build fast, async REST APIs with Python and FastAPI.", "skills": ["Python", "FastAPI"]},
            {"title": "Advanced SQL Queries", "type": "tutorial", "description": "Master SQL window functions, CTEs, and complex joins.", "skills": ["SQL"]},
            {"title": "Introduction to Machine Learning", "type": "course", "description": "A comprehensive introduction to machine learning concepts and algorithms.", "skills": ["Machine Learning", "Python"]},
            {"title": "Dockerizing Web Apps", "type": "tutorial", "description": "Learn how to containerize your python and javascript web applications.", "skills": ["Docker"]},
            {"title": "React Basics for Beginners", "type": "course", "description": "Get started with frontend web development using functional components in React.", "skills": ["React", "JavaScript"]},
            {"title": "Modern CSS Grid & Flexbox", "type": "tutorial", "description": "Master CSS layouts with Flexbox and CSS Grid.", "skills": ["CSS", "HTML"]},
            {"title": "Pandas Data Wrangling", "type": "tutorial", "description": "Clean, reshape, and analyze structured datasets using Pandas in Python.", "skills": ["Pandas", "Python", "Data Science"]},
            {"title": "Deep Learning with TensorFlow", "type": "course", "description": "Build and train neural networks using TensorFlow and Keras.", "skills": ["TensorFlow", "Machine Learning", "Python"]},
            {"title": "Deploying Apps on AWS", "type": "course", "description": "Deploy secure, scalable docker containers on AWS ECS and Fargate.", "skills": ["AWS", "Docker"]},
            {"title": "Building REST APIs", "type": "project", "description": "Build and deploy a REST API with FastAPI, SQL database, and SQLite.", "skills": ["FastAPI", "Python", "SQL"]},
            {"title": "E-commerce Dashboard in React", "type": "project", "description": "A functional admin dashboard built in React with CSS transitions.", "skills": ["React", "JavaScript", "CSS"]},
            {"title": "Predictive Modeling with Scikit-Learn", "type": "project", "description": "Apply machine learning regression and classification to solve real business problems.", "skills": ["Machine Learning", "Python", "Data Science"]},
            {"title": "Secure Docker Workflows", "type": "course", "description": "Advanced docker image optimization and secure container deployment.", "skills": ["Docker", "AWS"]},
            {"title": "Building a Custom Database", "type": "project", "description": "Write a basic toy relational database from scratch using Python and SQL interfaces.", "skills": ["SQL", "Python"]},
            {"title": "Interactive SVGs with CSS & JS", "type": "tutorial", "description": "Create animations using SVG, modern CSS, and vanilla JS.", "skills": ["CSS", "HTML", "JavaScript"]},
            {"title": "Time Series Analysis in Pandas", "type": "tutorial", "description": "Analyze temporal datasets, apply rolling windows, and forecast trends.", "skills": ["Pandas", "Data Science"]},
            {"title": "Reinforcement Learning Intro", "type": "course", "description": "Learn Q-learning and policy gradients with Gym environments.", "skills": ["Machine Learning", "TensorFlow"]},
            {"title": "Serverless APIs on AWS", "type": "project", "description": "Build lambda functions triggered by API Gateway with FastAPI adapter.", "skills": ["AWS", "FastAPI"]},
            {"title": "Full-Stack Python Web App", "type": "project", "description": "Combine a FastAPI backend with a React frontend and SQLite database.", "skills": ["Python", "FastAPI", "React", "SQL"]},
            {"title": "Web Scraping with BeautifulSoup", "type": "tutorial", "description": "Scrape static HTML websites and structure the extracted data.", "skills": ["Python", "HTML"]},
            {"title": "Kubernetes Orchestration", "type": "course", "description": "Orchestrate multi-container applications using Kubernetes clusters.", "skills": ["Docker", "AWS"]},
            {"title": "UI/UX CSS Styling Secrets", "type": "tutorial", "description": "Apply professional color palettes, glassmorphism, and responsive styling.", "skills": ["CSS"]}
        ]

        print("Creating content...")
        contents_map = {}
        for c in contents_data:
            content = ContentRepository.create(
                db, 
                title=c["title"], 
                content_type=c["type"], 
                description=c["description"], 
                skill_names=c["skills"]
            )
            contents_map[c["title"]] = content.id

        # Define Interactions (user-content feedback)
        # Note: 'click', 'bookmark', 'like', 'complete'
        interactions_data = [
            # Alice (interests: Python, FastAPI, SQL)
            {"user": "alice", "content": "FastAPI Crash Course", "type": "like", "rating": 5.0},
            {"user": "alice", "content": "Building REST APIs", "type": "click", "rating": 4.0},
            {"user": "alice", "content": "Full-Stack Python Web App", "type": "bookmark", "rating": None},
            {"user": "alice", "content": "Advanced SQL Queries", "type": "complete", "rating": 4.5},
            
            # Bob (interests: React, JavaScript, CSS)
            {"user": "bob", "content": "React Basics for Beginners", "type": "like", "rating": 4.5},
            {"user": "bob", "content": "Modern CSS Grid & Flexbox", "type": "complete", "rating": 4.0},
            {"user": "bob", "content": "E-commerce Dashboard in React", "type": "bookmark", "rating": None},
            {"user": "bob", "content": "UI/UX CSS Styling Secrets", "type": "click", "rating": 5.0},
            
            # Charlie (interests: Machine Learning, TensorFlow, Pandas, Python)
            {"user": "charlie", "content": "Introduction to Machine Learning", "type": "complete", "rating": 5.0},
            {"user": "charlie", "content": "Deep Learning with TensorFlow", "type": "like", "rating": 5.0},
            {"user": "charlie", "content": "Pandas Data Wrangling", "type": "click", "rating": 4.5},
            {"user": "charlie", "content": "Predictive Modeling with Scikit-Learn", "type": "bookmark", "rating": None},
            
            # Diana (interests: AWS, Docker, SQL)
            {"user": "diana", "content": "Dockerizing Web Apps", "type": "complete", "rating": 4.0},
            {"user": "diana", "content": "Deploying Apps on AWS", "type": "like", "rating": 4.5},
            {"user": "diana", "content": "Secure Docker Workflows", "type": "like", "rating": 5.0},
            {"user": "diana", "content": "Kubernetes Orchestration", "type": "click", "rating": None},
            
            # Ethan (interests: Python, SQL)
            {"user": "ethan", "content": "Advanced SQL Queries", "type": "like", "rating": 4.0},
            {"user": "ethan", "content": "Building a Custom Database", "type": "complete", "rating": 4.5},
            {"user": "ethan", "content": "Pandas Data Wrangling", "type": "click", "rating": 3.5},
            
            # Fiona (interests: React, HTML, CSS, JavaScript)
            {"user": "fiona", "content": "React Basics for Beginners", "type": "complete", "rating": 5.0},
            {"user": "fiona", "content": "Interactive SVGs with CSS & JS", "type": "like", "rating": 4.5},
            {"user": "fiona", "content": "UI/UX CSS Styling Secrets", "type": "bookmark", "rating": None},
            {"user": "fiona", "content": "Modern CSS Grid & Flexbox", "type": "click", "rating": 4.0},
            
            # George (interests: Data Science, Pandas, Machine Learning)
            {"user": "george", "content": "Pandas Data Wrangling", "type": "complete", "rating": 4.0},
            {"user": "george", "content": "Predictive Modeling with Scikit-Learn", "type": "like", "rating": 4.5},
            {"user": "george", "content": "Time Series Analysis in Pandas", "type": "bookmark", "rating": None},
            
            # Hannah (interests: Docker, AWS)
            {"user": "hannah", "content": "Deploying Apps on AWS", "type": "complete", "rating": 4.0},
            {"user": "hannah", "content": "Kubernetes Orchestration", "type": "like", "rating": 4.5},
            {"user": "hannah", "content": "Dockerizing Web Apps", "type": "click", "rating": 4.0},
            
            # Ian (interests: FastAPI, Docker, Python)
            {"user": "ian", "content": "FastAPI Crash Course", "type": "complete", "rating": 4.5},
            {"user": "ian", "content": "Dockerizing Web Apps", "type": "like", "rating": 4.0},
            {"user": "ian", "content": "Building REST APIs", "type": "click", "rating": 4.0}
        ]

        print("Creating interactions...")
        for inter in interactions_data:
            InteractionRepository.create(
                db,
                user_id=users_map[inter["user"]],
                content_id=contents_map[inter["content"]],
                interaction_type=inter["type"],
                rating=inter["rating"]
            )

        print("Seeding database complete.")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed()
