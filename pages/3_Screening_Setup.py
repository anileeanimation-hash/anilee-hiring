import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_screening_questions, toggle_question, update_question_weight, add_question, delete_question
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

# ── ADD CUSTOM QUESTION ───────────────────────────────────────────────────────
st.markdown("""
<div style="background:#e8f5e9; border:1px solid #4CAF50; padding:12px 16px;
            border-radius:8px; margin-bottom:12px;">
    <b>➕ Add Your Own Question</b><br>
    <small>HR can add any custom question here. It will appear on the screening form and
    AI will score it automatically.</small>
</div>""", unsafe_allow_html=True)

with st.form("add_custom_question_form", clear_on_submit=True):
    new_q = st.text_area(
        "Your Question *",
        placeholder="e.g. Do you have a two-wheeler for field visits?",
        height=90
    )
    cq1, cq2, cq3 = st.columns(3)
    with cq1:
        new_cat = st.text_input("Category", value="Custom",
                                help="Group label e.g. Logistics, Skills, Custom")
    with cq2:
        new_type = st.selectbox("Question Type",
                                ["Scoring (AI rates 0–10)", "Hard Filter (Pass/Fail)"])
    with cq3:
        new_weight = st.selectbox("Importance", [1, 2, 3],
                                  format_func=lambda x: {1: "1 — Normal", 2: "2 — Important",
                                                          3: "3 — Critical"}[x])

    submitted = st.form_submit_button("➕ Add Question", type="primary", use_container_width=True)
    if submitted:
        if not new_q.strip():
            st.warning("⚠️ Please type your question first.")
        else:
            is_hf = 1 if "Hard Filter" in new_type else 0
            add_question(new_q, new_cat, is_hf, new_weight)
            st.success(f"✅ Question added: \"{new_q.strip()[:60]}{'...' if len(new_q) > 60 else ''}\"")
            st.rerun()

# ── CUSTOM QUESTIONS — DELETE ─────────────────────────────────────────────────
custom_qs = [q for q in get_screening_questions() if q["category"] == "Custom"
             or q["id"] > 15]   # questions beyond the default 15 are custom
if custom_qs:
    st.markdown("**Your Custom Questions** *(click 🗑️ to remove)*")
    for q in custom_qs:
        col_q, col_del = st.columns([8, 1])
        with col_q:
            badge = "🚨 Hard Filter" if q["is_hard_filter"] else "📊 Scoring"
            st.markdown(
                f"<div style='padding:8px 12px;background:#fff;border:1px solid #ddd;"
                f"border-radius:6px;margin:3px 0;font-size:14px;'>"
                f"<span style='background:#6c757d;color:white;padding:1px 7px;"
                f"border-radius:8px;font-size:11px;margin-right:8px;'>{badge}</span>"
                f"{q['question']}</div>",
                unsafe_allow_html=True
            )
        with col_del:
            st.markdown("<div style='margin-top:6px;'>", unsafe_allow_html=True)
            if st.button("🗑️", key=f"del_{q['id']}", help="Delete this question"):
                delete_question(q["id"])
                st.success("Question deleted.")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

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
