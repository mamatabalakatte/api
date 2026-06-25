import time
import logging
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Optional

from app.database.connection import get_db, init_db
from app.database.repository import UserRepository, ContentRepository, InteractionRepository
from app.engine.recommender import RecommenderEngine
from app.api.schemas import InteractionCreate, RecommendationItem, HealthResponse, MetricsResponse
from app.utils.evaluation import evaluate_system

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recommender_api")

app = FastAPI(
    title="GenAI Recommendation System API",
    description="Production-grade API with hybrid recommendation engine, caching, cold-start handling, and metrics evaluation.",
    version="1.0.0"
)

# Enable CORS for Streamlit frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Recommendation Engine orchestrator singleton
recommender = RecommenderEngine()

# Keep track of latency history for metrics (limit to last 1000 requests)
LATENCY_HISTORY: List[float] = []

@app.on_event("startup")
def startup_event():
    logger.info("Starting up FastAPI application...")
    init_db()
    logger.info("Database initialized.")

# Middleware for tracing requests and recording performance latency
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Store recommendation request latencies for evaluation
    if "/recommendations" in request.url.path:
        LATENCY_HISTORY.append(process_time * 1000.0)  # convert to ms
        if len(LATENCY_HISTORY) > 1000:
            LATENCY_HISTORY.pop(0)
            
    logger.info(f"{request.method} {request.url.path} completed in {process_time:.4f}s with status {response.status_code}")
    return response

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Verifies backend operational status and SQLite database connection health."""
    db_connected = False
    try:
        # Simple query to check connection
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        
    return {
        "status": "healthy" if db_connected else "degraded",
        "database_connected": db_connected,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/recommendations", response_model=List[RecommendationItem], tags=["Core Recommendations"])
def get_recommendations(
    user_id: int = Query(..., description="ID of the user to get recommendations for"),
    n: int = Query(5, description="Number of recommendations to fetch", ge=1, le=20),
    simulated_skills: Optional[str] = Query(None, description="Comma-separated skills to simulate user interests for testing"),
    db: Session = Depends(get_db)
):
    """
    Retrieves personalized content recommendations for a user.
    Handles cold-start users dynamically and incorporates hybrid scoring.
    Supports on-the-fly interest skill override simulation.
    """
    # Verify user exists
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} does not exist.")
        
    try:
        skills_list = [s.strip() for s in simulated_skills.split(",") if s.strip()] if simulated_skills else None
        recs = recommender.get_recommendations(db, user_id=user_id, n=n, simulated_skills=skills_list)
        return recs
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error generating recommendations.")

@app.post("/feedback", tags=["Core Recommendations"])
def submit_feedback(interaction: InteractionCreate, db: Session = Depends(get_db)):
    """
    Submits user interaction feedback (click, bookmark, complete, like, or rating).
    Automatically invalidates the recommender cache for this user to update future calculations.
    """
    # Verify user and content exists
    user = UserRepository.get_by_id(db, interaction.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {interaction.user_id} does not exist.")
        
    content = ContentRepository.get_by_id(db, interaction.content_id)
    if not content:
        raise HTTPException(status_code=404, detail=f"Content with ID {interaction.content_id} does not exist.")

    try:
        # Save to DB
        new_inter = InteractionRepository.create(
            db, 
            user_id=interaction.user_id, 
            content_id=interaction.content_id, 
            interaction_type=interaction.interaction_type,
            rating=interaction.rating
        )
        
        # Invalidate cache for the user immediately to capture new interaction state
        recommender.invalidate_cache(user_id=interaction.user_id)
        logger.info(f"Feedback recorded. Invalided recommendation cache for user {interaction.user_id}.")
        
        return {
            "status": "success",
            "message": "Feedback recorded and cache invalidated.",
            "interaction_id": new_inter.id
        }
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save interaction feedback.")

@app.get("/users", tags=["Metadata"])
def list_users(db: Session = Depends(get_db)):
    """Lists all users in the system."""
    users = UserRepository.list_all(db)
    return [u.to_dict() for u in users]

@app.get("/content", tags=["Metadata"])
def list_content(db: Session = Depends(get_db)):
    """Lists all content items in the system."""
    contents = ContentRepository.list_all(db)
    return [c.to_dict() for c in contents]

@app.get("/metrics", response_model=MetricsResponse, tags=["Analytics"])
def get_system_metrics(db: Session = Depends(get_db)):
    """
    Runs an offline 80/20 train/test evaluation split over users with history.
    Computes average Precision@5, Recall@5, NDCG@5, and reports average API recommendation latency.
    """
    try:
        # Run system evaluation
        eval_results = evaluate_system(db, recommender, k=5)
        
        total_users = len(UserRepository.list_all(db))
        total_contents = len(ContentRepository.list_all(db))
        
        # Calculate average latency from history (in ms)
        avg_latency = sum(LATENCY_HISTORY) / len(LATENCY_HISTORY) if LATENCY_HISTORY else 0.0
        
        return {
            "precision_at_5": eval_results["precision_at_k"],
            "recall_at_5": eval_results["recall_at_k"],
            "ndcg_at_5": eval_results["ndcg_at_k"],
            "evaluated_users": eval_results["evaluated_users"],
            "total_users": total_users,
            "total_contents": total_contents,
            "avg_latency_ms": round(avg_latency, 2),
            "status": eval_results["status"]
        }
    except Exception as e:
        logger.error(f"Error evaluating system metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compute system metrics.")
