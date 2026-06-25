import numpy as np
from typing import List, Set, Dict, Any
from sqlalchemy.orm import Session
from app.database.models import Interaction
from app.database.repository import UserRepository, ContentRepository, InteractionRepository

def precision_at_k(recommended_ids: List[int], actual_ids: Set[int], k: int) -> float:
    """Calculates Precision@K."""
    if not recommended_ids or not actual_ids or k <= 0:
        return 0.0
    top_k_recs = recommended_ids[:k]
    hits = len([rec for rec in top_k_recs if rec in actual_ids])
    return hits / k

def recall_at_k(recommended_ids: List[int], actual_ids: Set[int], k: int) -> float:
    """Calculates Recall@K."""
    if not recommended_ids or not actual_ids or k <= 0:
        return 0.0
    top_k_recs = recommended_ids[:k]
    hits = len([rec for rec in top_k_recs if rec in actual_ids])
    return hits / len(actual_ids)

def ndcg_at_k(recommended_ids: List[int], actual_ids: Set[int], k: int) -> float:
    """Calculates Normalized Discounted Cumulative Gain (NDCG)@K."""
    if not recommended_ids or not actual_ids or k <= 0:
        return 0.0
    top_k_recs = recommended_ids[:k]
    
    # Calculate DCG@K
    dcg = 0.0
    for i, rec_id in enumerate(top_k_recs):
        if rec_id in actual_ids:
            dcg += 1.0 / np.log2(i + 2)  # i + 2 since index is 0-based and we need log2(rank + 1) -> log2(i + 2)

    # Calculate Ideal DCG@K (all actual hits sorted at the top)
    idcg = 0.0
    for i in range(min(k, len(actual_ids))):
        idcg += 1.0 / np.log2(i + 2)

    if idcg == 0.0:
        return 0.0
    return dcg / idcg

def evaluate_system(db: Session, recommender, k: int = 5) -> Dict[str, Any]:
    """
    Performs offline evaluation of the recommendation system.
    Splits interactions 80/20 (train/test) per user, rebuilds recommendation lists,
    and returns averages for Precision@K, Recall@K, and NDCG@K.
    """
    all_users = UserRepository.list_all(db)
    all_interactions = InteractionRepository.list_all(db)
    
    if len(all_interactions) < 5:
        return {
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "ndcg_at_k": 0.0,
            "evaluated_users": 0,
            "k": k,
            "status": "Insufficient interaction data to perform split."
        }

    # Group interactions by user
    user_interactions: Dict[int, List[Interaction]] = {}
    for inter in all_interactions:
        user_interactions.setdefault(inter.user_id, []).append(inter)

    train_interactions: List[Interaction] = []
    test_interactions_map: Dict[int, Set[int]] = {}  # user_id -> set of test content_ids
    
    # Split: For each user, put 20% of interactions in test, rest in train
    # Sort interactions by timestamp or ID to keep it deterministic
    np.random.seed(42)  # for reproducibility
    
    for u_id, inters in user_interactions.items():
        if len(inters) < 2:
            # If user has only 1 interaction, keep it in train
            train_interactions.extend(inters)
            continue
            
        # Shuffle index or just split
        n_test = max(1, int(len(inters) * 0.2))
        shuffled_indices = np.random.permutation(len(inters))
        
        test_indices = set(shuffled_indices[:n_test])
        
        for idx, inter in enumerate(inters):
            if idx in test_indices:
                test_interactions_map.setdefault(u_id, set()).add(inter.content_id)
            else:
                train_interactions.append(inter)

    # Evaluate for each user in the test set
    precisions = []
    recalls = []
    ndcgs = []
    
    # We evaluate users who have test interactions
    evaluated_users_count = 0
    
    for u_id, test_content_ids in test_interactions_map.items():
        if not test_content_ids:
            continue
            
        try:
            # Generate recommendations using only the training interactions
            # We pass the custom train interactions to the recommender
            recs_data = recommender.get_recommendations_with_custom_interactions(
                db=db, 
                user_id=u_id, 
                custom_interactions=train_interactions, 
                n=k
            )
            
            rec_ids = [r["content"]["id"] for r in recs_data]
            
            p = precision_at_k(rec_ids, test_content_ids, k)
            r = recall_at_k(rec_ids, test_content_ids, k)
            n_val = ndcg_at_k(rec_ids, test_content_ids, k)
            
            precisions.append(p)
            recalls.append(r)
            ndcgs.append(n_val)
            evaluated_users_count += 1
        except Exception as err:
            # Fallback or skip if errors occur during recommendation (e.g. user missing)
            print(f"Error evaluating user {u_id}: {err}")
            continue

    avg_p = float(np.mean(precisions)) if precisions else 0.0
    avg_r = float(np.mean(recalls)) if recalls else 0.0
    avg_ndcg = float(np.mean(ndcgs)) if ndcgs else 0.0

    return {
        "precision_at_k": round(avg_p, 4),
        "recall_at_k": round(avg_r, 4),
        "ndcg_at_k": round(avg_ndcg, 4),
        "evaluated_users": evaluated_users_count,
        "k": k,
        "status": "Success"
    }
