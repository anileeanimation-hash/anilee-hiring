import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_screening_questions, toggle_question, update_question_weight
from utils.ai_screener import get_whatsapp_template

st.set_page_config(page_title="Screening Setup — Anilee Hiring", page_icon="⚙️", layout="wide")
st.title("⚙️ Screening Configuration")
st.caption("Select which questions to ask candidates. HR can toggle them on/off anytime.")

questions = get_screening_questions()
hard_filters = [q for q in questions if q["is_hard_filter"]]
soft_questions = [q for q in questions if not q["is_hard_filter"]]

# ── HARD FILTERS ──────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:#fff3cd; border:1px solid #ffc107; padding:12px 16px;
            border-radius:8px; margin-bottom:12px;">
    <b>🚨 Hard Filters — Mandatory Checks</b><br>
    <small>If a candidate fails <i>any</i> enabled hard filter, they are automatically rejected.
    These are basic eligibility criteria.</small>
</div>""", unsafe_allow_html=True)

for q in hard_filters:
    col1, col2 = st.columns([6, 1])
    with col1:
        enabled = st.checkbox(
            f"**{q['question']}**  \n`Category: {q['category']}`",
            value=bool(q["is_enabled"]),
            key=f"hf_{q['id']}"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        status = "✅ ON" if q["is_enabled"] else "❌ OFF"
        st.markdown(f"<small style='color:#888;'>{status}</small>", unsafe_allow_html=True)

    if bool(enabled) != bool(q["is_enabled"]):
        toggle_question(q["id"], enabled)
        st.rerun()

st.divider()

# ── SOFT SCORING QUESTIONS ────────────────────────────────────────────────────
st.markdown("""
<div style="background:#d1ecf1; border:1px solid #0dcaf0; padding:12px 16px;
            border-radius:8px; margin-bottom:12px;">
    <b>📊 Scoring Questions — AI Evaluated</b><br>
    <small>Enabled questions are asked during screening. Claude AI scores each answer 0–10
    and calculates a weighted total score to classify candidates as Hot / Warm / Cold.</small>
</div>""", unsafe_allow_html=True)

# Group by category
categories = list(dict.fromkeys(q["category"] for q in soft_questions))
for cat in categories:
    cat_questions = [q for q in soft_questions if q["category"] == cat]
    st.markdown(f"**{cat}**")
    for q in cat_questions:
        col1, col2, col3 = st.columns([5, 1, 1])
        with col1:
            enabled = st.checkbox(
                q["question"],
                value=bool(q["is_enabled"]),
                key=f"sq_{q['id']}"
            )
        with col2:
            weight = st.number_input(
                "Weight", min_value=1, max_value=5,
                value=int(q["weight"]),
                key=f"wt_{q['id']}",
                help="1=Low, 2=Medium, 3=High, 5=Critical"
            )
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            badge_color = "#198754" if q["is_enabled"] else "#6C757D"
            st.markdown(f"""<span style="background:{badge_color};color:white;
                         padding:2px 8px;border-radius:10px;font-size:11px;">
                         {'ON' if q['is_enabled'] else 'OFF'}</span>""",
                        unsafe_allow_html=True)

        if bool(enabled) != bool(q["is_enabled"]):
            toggle_question(q["id"], enabled)
            st.rerun()
        if weight != int(q["weight"]):
            update_question_weight(q["id"], weight)

st.divider()

# ── CURRENT CONFIG SUMMARY ────────────────────────────────────────────────────
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("Current Setup Summary")
    enabled_hf = [q for q in hard_filters if q["is_enabled"]]
    enabled_sq = [q for q in soft_questions if q["is_enabled"]]
    max_score = sum(10 * q["weight"] for q in enabled_sq)

    st.markdown(f"- 🚨 **{len(enabled_hf)}** hard filter(s) active")
    st.markdown(f"- 📊 **{len(enabled_sq)}** scoring question(s) active")
    st.markdown(f"- 🔢 Max possible weighted score: **{max_score}** pts → normalized to **100%**")
    st.markdown("")
    st.markdown("**Score Bands:**")
    st.markdown("""
    | Band | Score |
    |------|-------|
    | 🔥 Hot | ≥ 80% |
    | ✅ Warm | 60–79% |
    | ❄️ Cold | 40–59% |
    | ❌ Rejected | < 40% |
    """)

with col_r:
    st.subheader("WhatsApp Outreach Template")
    st.caption("Copy and send this to candidates on WhatsApp after they apply.")
    msg = get_whatsapp_template()
    st.text_area("Template (Marathi/Hindi/English mix)", msg, height=320, label_visibility="collapsed")
    st.download_button("📥 Download Template", msg, "whatsapp_template.txt", "text/plain")
    st.info("💡 Once you set up WATI/AiSensy integration, this will be sent automatically within 5 minutes of a candidate applying.")
