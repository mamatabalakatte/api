import streamlit as st
import requests
import os
import json
import time
import pandas as pd
import numpy as np

# Import database session for peer similarity calculation
from app.database.connection import SessionLocal
from app.database.models import Interaction, User

# Configure Streamlit page settings
st.set_page_config(
    page_title="HiDevs RecSystem | Analytics Hub",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Endpoint Configuration
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# Premium Custom CSS for Dark Theme & Glassmorphism Aesthetics
custom_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    h1, h2, h3, h4 {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        color: #ffffff;
    }

    /* Main Container Styles */
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }

    /* Sidebar glassmorphism */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b;
    }

    /* Recommendation Cards */
    .content-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .content-card:hover {
        transform: translateY(-4px);
        border-color: #3b82f6;
        box-shadow: 0 10px 30px rgba(59, 130, 246, 0.15);
    }

    /* Type Badge */
    .type-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 12px;
        letter-spacing: 0.05em;
    }
    .badge-tutorial { background-color: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-course { background-color: rgba(59, 130, 246, 0.15); color: #3b82f6; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-project { background-color: rgba(139, 92, 246, 0.15); color: #8b5cf6; border: 1px solid rgba(139, 92, 246, 0.3); }

    /* Skill Tags */
    .skill-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.7rem;
        background: #1e293b;
        color: #94a3b8;
        margin-right: 6px;
        margin-top: 6px;
        border: 1px solid #334155;
    }

    /* Metrics Panels */
    .metric-box {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.5) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #60a5fa, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Explanation Styling */
    .explanation-box {
        background-color: rgba(59, 130, 246, 0.08);
        border-left: 4px solid #3b82f6;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin-top: 12px;
        font-size: 0.85rem;
        color: #93c5fd;
    }
    .cached-badge {
        font-size: 0.7rem;
        font-weight: bold;
        color: #fbbf24;
        background: rgba(251, 191, 36, 0.1);
        border: 1px solid rgba(251, 191, 36, 0.3);
        padding: 2px 8px;
        border-radius: 4px;
        float: right;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# Helper function to query the API
def fetch_api(endpoint: str, method="GET", data=None):
    url = f"{API_URL}/{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        else:
            response = requests.post(url, json=data, timeout=5)
        
        if response.status_code == 200:
            return response.json(), True
        return response.text, False
    except Exception as e:
        return str(e), False

# Calculate user similarities dynamically from SQLite DB for Explainable AI
def get_peer_similarities(target_user_id: int):
    db = SessionLocal()
    try:
        users = db.query(User).all()
        interactions = db.query(Interaction).all()
        if not users or not interactions:
            return []
            
        user_ids = [u.id for u in users]
        usernames = {u.id: u.username for u in users}
        content_ids = list(set([i.content_id for i in interactions]))
        
        user_idx = {uid: i for i, uid in enumerate(user_ids)}
        content_idx = {cid: i for i, cid in enumerate(content_ids)}
        
        R = np.zeros((len(user_ids), len(content_ids)))
        weight_map = {"click": 1.0, "bookmark": 2.0, "complete": 4.0, "like": 5.0}
        
        for inter in interactions:
            u_id = inter.user_id
            c_id = inter.content_id
            if u_id in user_idx and c_id in content_idx:
                val = inter.rating if inter.rating else weight_map.get(inter.interaction_type, 1.0)
                R[user_idx[u_id], content_idx[c_id]] = max(R[user_idx[u_id], content_idx[c_id]], val)
                
        target_idx = user_idx.get(target_user_id)
        if target_idx is None:
            return []
            
        norms = np.linalg.norm(R, axis=1, keepdims=True)
        norms[norms == 0] = 1e-9
        R_norm = R / norms
        
        target_norm = R_norm[target_idx]
        similarities = np.dot(R_norm, target_norm)
        
        peer_sims = []
        for other_uid in user_ids:
            if other_uid == target_user_id:
                continue
            o_idx = user_idx[other_uid]
            sim = similarities[o_idx]
            if sim > 0.01:
                peer_sims.append((usernames[other_uid].capitalize(), sim))
                
        peer_sims.sort(key=lambda x: x[1], reverse=True)
        return peer_sims
    except Exception:
        return []
    finally:
        db.close()

# Header layout
col_logo, col_title = st.columns([1, 6])
with col_title:
    st.title("HiDevs Recommendation Hub")
    st.caption("GenAI Production Recommendation System & Analytics Dashboard")

# Sidebar navigation & health status
st.sidebar.markdown("<h2 style='text-align: center; color: #60a5fa;'>🎯 HiDevs Logo</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---", unsafe_allow_html=True)

# Check API health
health_data, is_healthy = fetch_api("health")
if is_healthy:
    status_indicator = "🟢 API Online" if health_data.get("status") == "healthy" else "🟡 API Degraded"
    st.sidebar.success(status_indicator)
else:
    st.sidebar.error("🔴 API Offline")
    st.sidebar.warning("FastAPI backend is offline. Run `python run.py` first.")
    if st.sidebar.button("Retry Connection"):
        st.experimental_rerun()

# Sidebar sections
menu_selection = st.sidebar.radio(
    "Navigation Menu",
    ["🎯 Get Recommendations", "💬 Provide Feedback", "📊 System Metrics", "⚡ Load Testing Suite"]
)

st.sidebar.markdown("---", unsafe_allow_html=True)
st.sidebar.subheader("System Architecture")
st.sidebar.info(
    "This hybrid engine serves content recommendations by combining "
    "collaborative user-user patterns and user skill alignment, "
    "while optimizing latencies under 200ms using smart caching."
)

if is_healthy:
    # Load metadata (users and content) from API
    users, _ = fetch_api("users")
    contents, _ = fetch_api("content")
    
    # Map usernames to IDs
    users_dict = {u["username"].capitalize(): u for u in users}
    contents_dict = {c["title"]: c for c in contents}
    
    if menu_selection == "🎯 Get Recommendations":
        st.subheader("🎯 Intelligent Recommendations & Explanations")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("### Select User Profile")
            selected_username = st.selectbox("Choose Learner:", list(users_dict.keys()))
            user_data = users_dict[selected_username]
            
            st.write("**User Details:**")
            st.write(f"- **User ID:** `{user_data['id']}`")
            
            # INNOVATIVE FEATURE: Interactive Skill Profile Simulator (What-If analysis)
            st.markdown("---")
            st.markdown("#### 🛠️ Skill Profile Simulator")
            st.caption("Override user interest skills on the fly to see how recommendations adapt in real time.")
            
            all_db_skills = ["Python", "SQL", "FastAPI", "Docker", "Machine Learning", "Data Science", "React", "JavaScript", "Pandas", "TensorFlow", "CSS", "HTML", "AWS"]
            simulated_skills = st.multiselect(
                "Active Interests:",
                options=all_db_skills,
                default=user_data["skills"]
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            n_recs = st.slider("Max items to suggest:", min_value=1, max_value=10, value=5)
            
            # INNOVATIVE FEATURE: Peer Similarity Heatmap/Table (Explainable AI)
            st.markdown("---")
            st.markdown("#### 👥 Top Peer Similarities")
            st.caption("Users with similar learning patterns based on interaction weights (likes, completes).")
            
            peers = get_peer_similarities(user_data["id"])
            if peers:
                for peer_name, sim_score in peers[:3]:
                    st.write(f"**{peer_name}**")
                    st.progress(float(sim_score))
                    st.caption(f"Overlap index: {sim_score * 100:.1f}%")
            else:
                st.write("*No overlapping peers found yet. Submit feedback to train matrix.*")
                
        with col2:
            st.markdown(f"### Personalized Suggestions for {selected_username}")
            
            # Request recommendations with simulated skill overrides
            with st.spinner("Generating recommendations..."):
                start_time = time.time()
                skills_query = ",".join(simulated_skills) if simulated_skills else ""
                endpoint = f"recommendations?user_id={user_data['id']}&n={n_recs}"
                if skills_query:
                    endpoint += f"&simulated_skills={skills_query}"
                    
                recs_response, success = fetch_api(endpoint)
                latency_ms = (time.time() - start_time) * 1000.0
                
            if success and recs_response:
                # INNOVATIVE FEATURE: Real-time Latency Alert/Indicator
                latency_color = "#10b981" if latency_ms < 100 else "#fbbf24"
                st.markdown(
                    f"<p style='color: #94a3b8;'>Generated in <b style='color: {latency_color};'>{latency_ms:.2f}ms</b> (Target: &lt; 200ms)</p>", 
                    unsafe_allow_html=True
                )
                
                for rec in recs_response:
                    content_item = rec["content"]
                    score = rec["score"]
                    explanation = rec["explanation"]
                    method = rec["method"]
                    cached = rec["cached"]
                    
                    badge_class = f"badge-{content_item['type']}"
                    skills_tags = "".join([f'<span class="skill-tag">{s}</span>' for s in content_item["skills"]])
                    cached_html = '<span class="cached-badge">⚡ CACHED</span>' if cached else ''
                    
                    card_html = f"""
                    <div class="content-card">
                        {cached_html}
                        <span class="type-badge {badge_class}">{content_item['type']}</span>
                        <h4 style="margin: 4px 0 8px 0; font-size: 1.25rem;">{content_item['title']}</h4>
                        <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 12px;">{content_item['description']}</p>
                        <div>{skills_tags}</div>
                        
                        <div style="margin-top: 15px; display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 0.8rem; font-weight: bold; color: #a78bfa;">Match Score:</span>
                            <div style="background-color: #334155; width: 150px; height: 10px; border-radius: 5px; overflow: hidden; display: inline-block;">
                                <div style="background: linear-gradient(90deg, #60a5fa, #a78bfa); width: {min(100, int(score * 100))}%; height: 100%;"></div>
                            </div>
                            <span style="font-size: 0.85rem; color: #e2e8f0; font-weight: bold;">{score:.2f}</span>
                            <span style="font-size: 0.75rem; color: #94a3b8; margin-left: auto;">via {method}</span>
                        </div>
                        
                        <div class="explanation-box">
                            💡 {explanation}
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.error("Could not fetch recommendations. Please verify user ID.")
                st.write(recs_response)

    elif menu_selection == "💬 Provide Feedback":
        st.subheader("💬 Record Learning Interaction & Feedback")
        st.write(
            "Submit user activities to train and update the collaborative recommendation model. "
            "Submitting feedback invalidates cached recommendations for this user in real time."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Feedback Form")
            fb_user = st.selectbox("Select Learner:", list(users_dict.keys()))
            fb_content = st.selectbox("Select Content Item:", list(contents_dict.keys()))
            fb_type = st.selectbox("Interaction Type:", ["click", "bookmark", "like", "complete"])
            
            has_rating = st.checkbox("Provide numeric rating?")
            rating = None
            if has_rating:
                rating = st.slider("Rating (1.0 to 5.0):", min_value=1.0, max_value=5.0, value=5.0, step=0.5)
                
            submit_btn = st.button("Submit Interaction", use_container_width=True)
            
            if submit_btn:
                u_id = users_dict[fb_user]["id"]
                c_id = contents_dict[fb_content]["id"]
                
                post_data = {
                    "user_id": u_id,
                    "content_id": c_id,
                    "interaction_type": fb_type,
                    "rating": rating
                }
                
                res, success = fetch_api("feedback", method="POST", data=post_data)
                if success:
                    st.success("🎉 Interaction feedback submitted and registered successfully!")
                    st.balloons()
                    st.info(f"Recommendation cache cleared for user **{fb_user}**. The next recommendation request will compute updated parameters.")
                else:
                    st.error("Failed to submit feedback.")
                    st.write(res)
                    
        with col2:
            st.markdown("### Content Overview")
            selected_c = contents_dict[fb_content]
            st.write(f"**Title:** {selected_c['title']}")
            st.write(f"**ID:** `{selected_c['id']}`")
            st.write(f"**Type:** `{selected_c['type'].upper()}`")
            st.write(f"**Description:** {selected_c['description']}")
            skills_html = "".join([f'<span class="skill-tag">{s}</span>' for s in selected_c["skills"]])
            st.markdown(f"**Covered Skills:**<br>{skills_html}", unsafe_allow_html=True)

    elif menu_selection == "📊 System Metrics":
        st.subheader("📊 Model Performance & Offline Evaluation Metrics")
        st.write(
            "Evaluation metrics are calculated by running an offline 80/20 train/test split. "
            "We generate recommendations using only 80% training interactions, and test relevance against the 20% test interactions."
        )
        
        with st.spinner("Calculating performance metrics..."):
            metrics, success = fetch_api("metrics")
            
        if success:
            m_col1, m_col2, m_col3 = st.columns(3)
            
            with m_col1:
                st.markdown(
                    f"""<div class="metric-box">
                        <div class="metric-value">{metrics['precision_at_5'] * 100:.1f}%</div>
                        <div class="metric-label">Precision@5</div>
                        <p style="font-size:0.75rem; color:#64748b; margin-top:8px;">% of recommended items that are relevant</p>
                    </div>""",
                    unsafe_allow_html=True
                )
                
            with m_col2:
                st.markdown(
                    f"""<div class="metric-box">
                        <div class="metric-value">{metrics['recall_at_5'] * 100:.1f}%</div>
                        <div class="metric-label">Recall@5</div>
                        <p style="font-size:0.75rem; color:#64748b; margin-top:8px;">% of relevant items successfully recommended</p>
                    </div>""",
                    unsafe_allow_html=True
                )
                
            with m_col3:
                st.markdown(
                    f"""<div class="metric-box">
                        <div class="metric-value">{metrics['ndcg_at_5'] * 100:.1f}%</div>
                        <div class="metric-label">NDCG@5</div>
                        <p style="font-size:0.75rem; color:#64748b; margin-top:8px;">Normalized Discounted Cumulative Gain (ordering quality)</p>
                    </div>""",
                    unsafe_allow_html=True
                )
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("### Metadata Statistics")
            s_col1, s_col2, s_col3, s_col4 = st.columns(4)
            s_col1.metric("Evaluated Users", metrics["evaluated_users"])
            s_col2.metric("Total Users", metrics["total_users"])
            s_col3.metric("Total Content Items", metrics["total_contents"])
            s_col4.metric("Avg Req Latency", f"{metrics['avg_latency_ms']} ms")
            
            st.write(f"**Evaluation Status:** `{metrics['status']}`")
        else:
            st.error("Could not fetch metrics.")
            st.write(metrics)

    elif menu_selection == "⚡ Load Testing Suite":
        st.subheader("⚡ System Concurrency & Load Testing")
        st.write(
            "Simulate **10 concurrent users** sending **20 requests each** (total 200 recommendation API calls) "
            "to evaluate uvicorn web server capacity and recommendation latency under concurrent load."
        )
        
        run_btn = st.button("🚀 Trigger Load Test Scenario", use_container_width=True)
        report_file = "load_test_report.json"
        
        if run_btn:
            with st.spinner("Simulating concurrent requests... Running python script..."):
                import subprocess
                result = subprocess.run(["python", "-m", "app.scripts.load_test"], capture_output=True, text=True)
                
            if result.returncode == 0:
                st.success("Load test completed successfully!")
            else:
                st.error("Error executing load test.")
                st.code(result.stderr)
                
        if os.path.exists(report_file):
            with open(report_file, "r") as f:
                report = json.load(f)
                
            if "error" in report:
                st.error(f"Last load test execution failed: {report['error']}")
            else:
                st.markdown("### Performance & Stress Test Report")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Throughput", f"{report['throughput_req_per_sec']} req/s")
                c2.metric("Successful / Total", f"{report['successful_requests']} / {report['total_requests']}")
                c3.metric("Avg Latency", f"{report['latency']['avg_ms']} ms")
                c4.metric("95th Percentile (P95)", f"{report['latency']['p95_ms']} ms")
                
                col_lat1, col_lat2 = st.columns(2)
                with col_lat1:
                    st.write("**Latency Percentiles:**")
                    lat_df = pd.DataFrame({
                        "Metric": ["Average", "Median (P50)", "P95 (95% of requests under)", "P99 (99% of requests under)", "Minimum", "Maximum"],
                        "Latency (ms)": [
                            report["latency"]["avg_ms"],
                            report["latency"]["p50_ms"],
                            report["latency"]["p95_ms"],
                            report["latency"]["p99_ms"],
                            report["latency"]["min_ms"],
                            report["latency"]["max_ms"]
                        ]
                    })
                    st.dataframe(lat_df, hide_index=True)
                    st.write(f"*Test run timestamp: {report['timestamp']}*")
                    
                with col_lat2:
                    st.write("**Latency Distribution Chart:**")
                    lats = report.get("all_successful_latencies", [])
                    if lats:
                        hist_values, bin_edges = np.histogram(lats, bins=10)
                        chart_df = pd.DataFrame({
                            "Latency Range (ms)": [f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}" for i in range(len(hist_values))],
                            "Request Count": hist_values
                        })
                        st.bar_chart(chart_df, x="Latency Range (ms)", y="Request Count")
                    else:
                        st.write("No latency details to plot.")
        else:
            st.info("No load test report found. Click 'Trigger Load Test Scenario' to run evaluation and display results.")

else:
    st.error("Unable to load dashboard because the FastAPI backend is not accessible.")
    st.info("Please start the FastAPI backend by running `python run.py` in your terminal.")
