import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.db import init_db, get_pipeline_stats, get_recent_activity

st.set_page_config(
    page_title="Anilee Academy — Hiring Portal",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database on every load
init_db()

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#FF6B35,#c0392b); padding:20px 24px; border-radius:10px; margin-bottom:16px;">
    <h1 style="color:white; margin:0; font-size:28px;">🎓 Anilee Academy — Hiring Portal</h1>
    <p style="color:rgba(255,255,255,0.85); margin:4px 0 0 0; font-size:14px;">
        Educational Counsellor Recruitment | Satara, Maharashtra
    </p>
</div>
""", unsafe_allow_html=True)

# ── METRICS ───────────────────────────────────────────────────────────────────
stats = get_pipeline_stats()

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Total in Pipeline", stats.get("total", 0))
with c2:
    hot = stats.get("hot", 0)
    st.metric("🔥 Hot Leads", hot, delta="Need interview" if hot > 0 else None)
with c3:
    st.metric("Active Screening", stats.get("screening", 0))
with c4:
    st.metric("Interviews Scheduled", stats.get("interviews", 0))
with c5:
    st.metric("Hired This Month", stats.get("hired", 0))

st.divider()

# ── MAIN CONTENT ──────────────────────────────────────────────────────────────
col_left, col_right = st.columns([2.2, 1])

with col_left:
    st.subheader("Recent Activity")
    activities = get_recent_activity(10)

    if not activities:
        st.info("No activity yet. Add your first candidate to get started.")
    else:
        icon_map = {
            "Added to Pipeline": "👤",
            "Stage Changed": "➡️",
            "Score Updated": "📊",
            "Interview Scheduled": "📅",
            "Interview Updated": "✏️",
            "Deleted": "🗑️",
        }
        for act in activities:
            icon = icon_map.get(act["action"], "📌")
            color = "#FF6B35" if act["action"] == "Score Updated" else (
                "#28A745" if "Hired" in act.get("details", "") else "#dee2e6"
            )
            st.markdown(f"""
            <div style="padding:10px 14px; margin:4px 0; background:#fff;
                        border-radius:8px; border-left:4px solid {color};
                        box-shadow:0 1px 3px rgba(0,0,0,0.06);">
                <b>{icon} {act['candidate_name']}</b>
                <span style="color:#555;"> — {act['action']}</span><br>
                <small style="color:#888;">{act['details'] or ''} &nbsp;•&nbsp; {act['created_at']}</small>
            </div>""", unsafe_allow_html=True)

with col_right:
    st.subheader("Quick Actions")
    if st.button("➕ Add New Candidate", use_container_width=True, type="primary"):
        st.switch_page("pages/2_Candidates.py")
    if st.button("📊 View Full Pipeline", use_container_width=True):
        st.switch_page("pages/1_Pipeline.py")
    if st.button("📅 Schedule Interview", use_container_width=True):
        st.switch_page("pages/4_Interviews.py")
    if st.button("⚙️ Screening Setup", use_container_width=True):
        st.switch_page("pages/3_Screening_Setup.py")
    if st.button("📈 Analytics", use_container_width=True):
        st.switch_page("pages/5_Analytics.py")

    st.divider()
    total = max(stats.get("total", 1), 1)
    hired = stats.get("hired", 0)
    conversion = int((hired / total) * 100)
    rejected = stats.get("rejected", 0)

    st.subheader("Pipeline Health")
    st.metric("Conversion Rate", f"{conversion}%")
    st.metric("Rejected Candidates", rejected)

    # API key status
    st.divider()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass

    if api_key:
        st.success("✅ AI Screening: Active")
    else:
        st.warning("⚠️ AI Screening: API key not set")
        with st.expander("How to set up AI screening"):
            st.markdown("""
            Create `.streamlit/secrets.toml` in the project folder:
            ```toml
            ANTHROPIC_API_KEY = "sk-ant-..."
            ```
            Or set the environment variable:
            ```bash
            export ANTHROPIC_API_KEY="sk-ant-..."
            ```
            """)
