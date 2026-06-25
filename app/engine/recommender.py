import time
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Set
from sqlalchemy.orm import Session
from app.database.models import User, Content, Interaction, Skill
from app.database.repository import UserRepository, ContentRepository, InteractionRepository

class RecommenderEngine:
    def __init__(self):
        # In-memory recommendation cache: { (user_id, n): (recommendations_list, cache_time) }
        self._cache: Dict[Tuple[int, int], Tuple[List[Dict[str, Any]], float]] = {}
        # Cache duration: 60 seconds
        self.cache_ttl = 60.0

    def invalidate_cache(self, user_id: int = None):
        """Invalidates cache. If user_id is provided, invalidates recommendations for that user."""
        if user_id is not None:
            keys_to_remove = [k for k in self._cache.keys() if k[0] == user_id]
            for k in keys_to_remove:
                self._cache.pop(k, None)
        else:
            self._cache.clear()

    def get_recommendations(self, db: Session, user_id: int, n: int = 5, simulated_skills: List[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves recommendations for a user. First checks cache.
        If simulated_skills is provided, bypasses cache to calculate dynamically.
        """
        if simulated_skills is not None:
            recs = self._get_recommendations_uncached(db, user_id, n, simulated_skills)
            return [{"cached": False, **rec} for rec in recs]

        now = time.time()
        cache_key = (user_id, n)
        
        if cache_key in self._cache:
            recs, cached_time = self._cache[cache_key]
            if now - cached_time < self.cache_ttl:
                return [{"cached": True, **rec} for rec in recs]
        
        recs = self._get_recommendations_uncached(db, user_id, n)
        self._cache[cache_key] = (recs, now)
        return [{"cached": False, **rec} for rec in recs]

    def _get_recommendations_uncached(self, db: Session, user_id: int, n: int, simulated_skills: List[str] = None) -> List[Dict[str, Any]]:
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        all_contents = ContentRepository.list_all(db)
        if not all_contents:
            return []

        user_interactions = InteractionRepository.get_by_user_id(db, user_id)
        interacted_content_ids = {i.content_id for i in user_interactions}

        # Resolve the active skills for this recommendation request
        if simulated_skills is not None:
            user_skills = {s.strip().lower() for s in simulated_skills}
        else:
            user_skills = {s.name.lower() for s in user.skills}

        # 1. Cold Start Handlers
        if not user_interactions:
            if user_skills:
                return self._recommend_cold_start_skills(user_skills, all_contents, n)
            else:
                return self._recommend_cold_start_popularity(db, all_contents, n)

        # 2. Warm User: Hybrid recommendation
        return self._recommend_hybrid(db, user, user_skills, all_contents, user_interactions, interacted_content_ids, n)

    def _recommend_cold_start_skills(self, user_skills: Set[str], all_contents: List[Content], n: int) -> List[Dict[str, Any]]:
        """Recommends items based on user skills overlap (Jaccard similarity)."""
        recommendations = []

        for content in all_contents:
            content_skills = {s.name.lower() for s in content.skills}
            
            intersection = user_skills.intersection(content_skills)
            union = user_skills.union(content_skills)
            
            jaccard_score = len(intersection) / len(union) if union else 0.0
            
            if jaccard_score > 0:
                matching_skills = [s.name for s in content.skills if s.name.lower() in user_skills]
                explanation = f"Recommended because it aligns with your interest in: {', '.join(matching_skills)}."
                recommendations.append({
                    "content": content.to_dict(),
                    "score": round(jaccard_score, 4),
                    "explanation": explanation,
                    "method": "Content-Based (Skills Overlap)"
                })

        recommendations.sort(key=lambda x: x["score"], reverse=True)
        
        if len(recommendations) < n:
            pad_count = n - len(recommendations)
            already_recommended_ids = {r["content"]["id"] for r in recommendations}
            popular_items = self._get_popular_items_excluding(all_contents, already_recommended_ids, pad_count)
            
            for item, score in popular_items:
                recommendations.append({
                    "content": item.to_dict(),
                    "score": round(score, 4),
                    "explanation": "Recommended because it is popular among other active users.",
                    "method": "Popularity Fallback"
                })

        return recommendations[:n]

    def _recommend_cold_start_popularity(self, db: Session, all_contents: List[Content], n: int) -> List[Dict[str, Any]]:
        """Recommends the most popular items globally."""
        all_interactions = InteractionRepository.list_all(db)
        
        popularity: Dict[int, float] = {}
        for inter in all_interactions:
            weight = 1.0
            if inter.interaction_type == "complete":
                weight = 3.0
            elif inter.interaction_type == "like":
                weight = 2.5
            elif inter.interaction_type == "bookmark":
                weight = 2.0
            
            if inter.rating:
                weight += inter.rating / 5.0
                
            popularity[inter.content_id] = popularity.get(inter.content_id, 0.0) + weight

        scored_contents = []
        for content in all_contents:
            score = popularity.get(content.id, 0.0)
            scored_contents.append((content, score))
            
        scored_contents.sort(key=lambda x: x[1], reverse=True)
        
        recs = []
        max_score = scored_contents[0][1] if scored_contents else 1.0
        if max_score == 0:
            max_score = 1.0
            
        for content, score in scored_contents[:n]:
            norm_score = score / max_score
            recs.append({
                "content": content.to_dict(),
                "score": round(norm_score, 4),
                "explanation": "Recommended because it is highly popular in the community.",
                "method": "Popularity-Based"
            })
        return recs

    def _get_popular_items_excluding(self, all_contents: List[Content], exclude_ids: Set[int], count: int) -> List[Tuple[Content, float]]:
        candidates = [c for c in all_contents if c.id not in exclude_ids]
        candidates.sort(key=lambda x: len(x.skills), reverse=True)
        
        results = []
        for i, item in enumerate(candidates[:count]):
            score = 0.5 - (i * 0.05)
            results.append((item, max(0.1, score)))
        return results

    def _recommend_hybrid(self, db: Session, user: User, user_skills: Set[str], all_contents: List[Content], 
                          user_interactions: List[Interaction], interacted_content_ids: Set[int], n: int) -> List[Dict[str, Any]]:
        all_users = UserRepository.list_all(db)
        all_interactions = InteractionRepository.list_all(db)

        # 1. CONTENT-BASED SCORE (CB)
        cb_scores: Dict[int, float] = {}
        for content in all_contents:
            if content.id in interacted_content_ids:
                continue
            content_skills = {s.name.lower() for s in content.skills}
            intersection = user_skills.intersection(content_skills)
            union = user_skills.union(content_skills)
            cb_scores[content.id] = len(intersection) / len(union) if union else 0.0

        # 2. COLLABORATIVE FILTERING SCORE (CF)
        cf_scores = self._compute_collaborative_filtering(user.id, all_users, all_contents, all_interactions, interacted_content_ids)

        # 3. COMBINE SCORES (HYBRID)
        hybrid_recommendations = []
        alpha = 0.5

        for content in all_contents:
            if content.id in interacted_content_ids:
                continue
                
            cb_val = cb_scores.get(content.id, 0.0)
            cf_val = cf_scores.get(content.id, 0.0)
            
            hybrid_score = (alpha * cf_val) + ((1 - alpha) * cb_val)
            
            matching_skills = [s.name for s in content.skills if s.name.lower() in user_skills]
            
            if cb_val > 0.4 and cf_val > 0.4:
                explanation = f"Matches your interest in {', '.join(matching_skills[:2])} and is popular among similar learners."
                method = "Hybrid (Collaborative + Content-Based)"
            elif cf_val > cb_val and cf_val > 0.2:
                explanation = "Users with similar learning patterns highly engaged with this content."
                method = "Collaborative Filtering"
            elif cb_val > 0:
                explanation = f"Recommended because it teaches: {', '.join(matching_skills[:3])}."
                method = "Content-Based (Skills)"
            else:
                explanation = "Recommended based on general trends and matching details."
                method = "Hybrid Fallback"

            hybrid_recommendations.append({
                "content": content.to_dict(),
                "score": round(hybrid_score, 4),
                "explanation": explanation,
                "method": method
            })

        hybrid_recommendations.sort(key=lambda x: x["score"], reverse=True)
        return hybrid_recommendations[:n]

    def _compute_collaborative_filtering(self, target_user_id: int, all_users: List[User], all_contents: List[Content], 
                                         all_interactions: List[Interaction], interacted_ids: Set[int]) -> Dict[int, float]:
        user_ids = [u.id for u in all_users]
        content_ids = [c.id for c in all_contents]
        
        if len(user_ids) < 2 or not all_interactions:
            return {}

        user_idx = {uid: i for i, uid in enumerate(user_ids)}
        content_idx = {cid: i for i, cid in enumerate(content_ids)}

        R = np.zeros((len(user_ids), len(content_ids)))
        weight_map = {"click": 1.0, "bookmark": 2.0, "complete": 4.0, "like": 5.0}

        for inter in all_interactions:
            u_id = inter.user_id
            c_id = inter.content_id
            if u_id in user_idx and c_id in content_idx:
                val = inter.rating if inter.rating else weight_map.get(inter.interaction_type, 1.0)
                R[user_idx[u_id], content_idx[c_id]] = max(R[user_idx[u_id], content_idx[c_id]], val)

        target_idx = user_idx.get(target_user_id)
        if target_idx is None:
            return {}

        norms = np.linalg.norm(R, axis=1, keepdims=True)
        norms[norms == 0] = 1e-9
        R_norm = R / norms
        
        target_norm = R_norm[target_idx]
        similarities = np.dot(R_norm, target_norm)
        
        predicted_scores = {}
        for c_id in content_ids:
            if c_id in interacted_ids:
                continue
                
            c_idx = content_idx[c_id]
            weighted_sum = 0.0
            similarity_sum = 0.0
            
            for other_uid in user_ids:
                if other_uid == target_user_id:
                    continue
                    
                o_idx = user_idx[other_uid]
                sim = similarities[o_idx]
                
                if sim > 0:
                    rating = R[o_idx, c_idx]
                    if rating > 0:
                        weighted_sum += sim * rating
                        similarity_sum += sim
            
            if similarity_sum > 0:
                predicted_scores[c_id] = (weighted_sum / similarity_sum) / 5.0
            else:
                predicted_scores[c_id] = 0.0
                
        return predicted_scores

    def get_recommendations_with_custom_interactions(self, db: Session, user_id: int, 
                                                    custom_interactions: List[Interaction], n: int = 5) -> List[Dict[str, Any]]:
        """
        Generates recommendations bypasses cache, using custom train-interactions list instead of database queries.
        Used for validation and metrics calculation.
        """
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        all_contents = ContentRepository.list_all(db)
        if not all_contents:
            return []

        user_inters = [i for i in custom_interactions if i.user_id == user_id]
        interacted_content_ids = {i.content_id for i in user_inters}
        user_skills = {s.name.lower() for s in user.skills}

        if not user_inters:
            if user_skills:
                return self._recommend_cold_start_skills(user_skills, all_contents, n)
            else:
                return self._recommend_cold_start_popularity_with_custom(all_contents, custom_interactions, n)

        # Warm User hybrid recommendation
        cb_scores: Dict[int, float] = {}
        for content in all_contents:
            if content.id in interacted_content_ids:
                continue
            content_skills = {s.name.lower() for s in content.skills}
            intersection = user_skills.intersection(content_skills)
            union = user_skills.union(content_skills)
            cb_scores[content.id] = len(intersection) / len(union) if union else 0.0

        all_users = UserRepository.list_all(db)
        cf_scores = self._compute_collaborative_filtering_with_custom(
            user_id, all_users, all_contents, custom_interactions, interacted_content_ids
        )

        hybrid_recommendations = []
        alpha = 0.5
        for content in all_contents:
            if content.id in interacted_content_ids:
                continue
            cb_val = cb_scores.get(content.id, 0.0)
            cf_val = cf_scores.get(content.id, 0.0)
            hybrid_score = (alpha * cf_val) + ((1 - alpha) * cb_val)
            
            matching_skills = [s.name for s in content.skills if s.name.lower() in user_skills]
            if cb_val > 0.4 and cf_val > 0.4:
                explanation = f"Matches interest in {', '.join(matching_skills[:2])} and popular among similar learners."
                method = "Hybrid (CF + CB)"
            elif cf_val > cb_val and cf_val > 0.2:
                explanation = "Similar users also liked this."
                method = "Collaborative Filtering"
            elif cb_val > 0:
                explanation = f"Teaches your interest skills: {', '.join(matching_skills[:2])}"
                method = "Content-Based"
            else:
                explanation = "Recommended based on general trends."
                method = "Hybrid Fallback"

            hybrid_recommendations.append({
                "content": content.to_dict(),
                "score": round(hybrid_score, 4),
                "explanation": explanation,
                "method": method
            })

        hybrid_recommendations.sort(key=lambda x: x["score"], reverse=True)
        return hybrid_recommendations[:n]

    def _recommend_cold_start_popularity_with_custom(self, all_contents: List[Content], 
                                                     custom_interactions: List[Interaction], n: int) -> List[Dict[str, Any]]:
        popularity: Dict[int, float] = {}
        weight_map = {"click": 1.0, "bookmark": 2.0, "complete": 4.0, "like": 5.0}
        for inter in custom_interactions:
            val = inter.rating if inter.rating else weight_map.get(inter.interaction_type, 1.0)
            popularity[inter.content_id] = popularity.get(inter.content_id, 0.0) + val

        scored_contents = []
        for content in all_contents:
            score = popularity.get(content.id, 0.0)
            scored_contents.append((content, score))
            
        scored_contents.sort(key=lambda x: x[1], reverse=True)
        max_score = scored_contents[0][1] if scored_contents else 1.0
        if max_score == 0:
            max_score = 1.0

        recs = []
        for content, score in scored_contents[:n]:
            recs.append({
                "content": content.to_dict(),
                "score": round(score / max_score, 4),
                "explanation": "Recommended because it is popular among other active users.",
                "method": "Popularity-Based"
            })
        return recs

    def _compute_collaborative_filtering_with_custom(self, target_user_id: int, all_users: List[User], 
                                                     all_contents: List[Content], custom_interactions: List[Interaction], 
                                                     interacted_ids: Set[int]) -> Dict[int, float]:
        user_ids = [u.id for u in all_users]
        content_ids = [c.id for c in all_contents]
        if len(user_ids) < 2 or not custom_interactions:
            return {}

        user_idx = {uid: i for i, uid in enumerate(user_ids)}
        content_idx = {cid: i for i, cid in enumerate(content_ids)}

        R = np.zeros((len(user_ids), len(content_ids)))
        weight_map = {"click": 1.0, "bookmark": 2.0, "complete": 4.0, "like": 5.0}

        for inter in custom_interactions:
            u_id = inter.user_id
            c_id = inter.content_id
            if u_id in user_idx and c_id in content_idx:
                val = inter.rating if inter.rating else weight_map.get(inter.interaction_type, 1.0)
                R[user_idx[u_id], content_idx[c_id]] = max(R[user_idx[u_id], content_idx[c_id]], val)

        target_idx = user_idx.get(target_user_id)
        if target_idx is None:
            return {}

        norms = np.linalg.norm(R, axis=1, keepdims=True)
        norms[norms == 0] = 1e-9
        R_norm = R / norms
        
        target_norm = R_norm[target_idx]
        similarities = np.dot(R_norm, target_norm)

        predicted_scores = {}
        for c_id in content_ids:
            if c_id in interacted_ids:
                continue
            c_idx = content_idx[c_id]
            weighted_sum = 0.0
            similarity_sum = 0.0
            for other_uid in user_ids:
                if other_uid == target_user_id:
                    continue
                o_idx = user_idx[other_uid]
                sim = similarities[o_idx]
                if sim > 0:
                    rating = R[o_idx, c_idx]
                    if rating > 0:
                        weighted_sum += sim * rating
                        similarity_sum += sim
            
            if similarity_sum > 0:
                predicted_scores[c_id] = (weighted_sum / similarity_sum) / 5.0
            else:
                predicted_scores[c_id] = 0.0
        return predicted_scores
