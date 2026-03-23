import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_candidates_by_stage, update_candidate_stage, STAGES

st.set_page_config(page_title="Pipeline — Anilee Hiring", page_icon="📊", layout="wide")
st.title("📊 Recruitment Pipeline")
st.caption("Visual overview of all candidates by stage")

STAGE_COLORS = {
    "New": "#6C757D",
    "Outreached": "#0D6EFD",
    "Screening": "#FFC107",
    "Screened": "#0DCAF0",
    "Interview Scheduled": "#FF6B35",
    "Hired": "#198754",
    "Rejected": "#DC3545",
}
STAGE_ICONS = {
    "New": "🆕", "Outreached": "📱", "Screening": "🔍",
    "Screened": "✅", "Interview Scheduled": "📅", "Hired": "🎉", "Rejected": "❌",
}
BAND_COLORS = {
    "Hot 🔥": "#DC3545", "Warm ✅": "#198754",
    "Cold ❄️": "#0D6EFD", "Rejected ❌": "#6C757D", "Unscored": "#ADB5BD",
}

by_stage = get_candidates_by_stage()

# ── SUMMARY BAR ───────────────────────────────────────────────────────────────
active_stages = ["New", "Outreached", "Screening", "Screened", "Interview Scheduled"]
cols = st.columns(len(active_stages))
for i, stage in enumerate(active_stages):
    count = len(by_stage.get(stage, []))
    color = STAGE_COLORS[stage]
    with cols[i]:
        st.markdown(f"""
        <div style="text-align:center; padding:14px 8px; background:{color}18;
                    border:2px solid {color}; border-radius:10px;">
            <div style="font-size:26px;">{STAGE_ICONS[stage]}</div>
            <div style="font-size:22px; font-weight:700; color:{color};">{count}</div>
            <div style="font-size:12px; color:#555; font-weight:500;">{stage}</div>
        </div>""", unsafe_allow_html=True)

st.divider()

# ── CONTROLS ─────────────────────────────────────────────────────────────────
show_rejected = st.toggle("Show Rejected", False)
display_stages = STAGES if show_rejected else [s for s in STAGES if s != "Rejected"]

# ── KANBAN COLUMNS ────────────────────────────────────────────────────────────
st.subheader("Candidates by Stage")

for batch_start in range(0, len(display_stages), 4):
    batch = display_stages[batch_start: batch_start + 4]
    cols = st.columns(len(batch))

    for j, stage in enumerate(batch):
        candidates = by_stage.get(stage, [])
        color = STAGE_COLORS[stage]

        with cols[j]:
            st.markdown(f"""
            <div style="background:{color}; color:white; padding:8px 12px;
                        border-radius:8px 8px 0 0; font-weight:600; font-size:14px;">
                {STAGE_ICONS[stage]} {stage} ({len(candidates)})
            </div>""", unsafe_allow_html=True)

            card_html = ""
            if not candidates:
                card_html = """<div style="border:1px dashed #ddd; padding:20px;
                    text-align:center; color:#bbb; font-size:12px;
                    border-radius:0 0 8px 8px;">Empty</div>"""
            else:
                cards = ""
                for cand in candidates[:12]:
                    band = cand.get("score_band") or "Unscored"
                    bc = BAND_COLORS.get(band, "#ADB5BD")
                    score_txt = f"{cand['score']}%" if cand.get("score", 0) > 0 else "—"
                    badge = (f'<span style="background:{bc};color:white;padding:1px 7px;'
                             f'border-radius:10px;font-size:10px;">{band}</span>'
                             if band != "Unscored" else "")
                    cards += f"""
                    <div style="border:1px solid #e0e0e0; padding:9px 10px; margin:5px 0;
                                border-radius:7px; background:white; border-left:3px solid {bc};">
                        <div style="font-weight:600;font-size:13px;">{cand.get('name','?')}</div>
                        <div style="font-size:11px;color:#666;">📱 {cand.get('phone','—')}</div>
                        <div style="font-size:11px;color:#888;margin-top:2px;">
                            {cand.get('source','—')} &nbsp;|&nbsp; Score: {score_txt}
                        </div>
                        <div style="margin-top:4px;">{badge}</div>
                    </div>"""
                if len(candidates) > 12:
                    cards += f'<div style="text-align:center;color:#aaa;font-size:11px;">+{len(candidates)-12} more</div>'
                card_html = f'<div style="border:1px solid #e0e0e0; border-top:none; border-radius:0 0 8px 8px; padding:6px;">{cards}</div>'

            st.markdown(card_html, unsafe_allow_html=True)

    if batch_start + 4 < len(display_stages):
        st.markdown("<br>", unsafe_allow_html=True)

# ── MOVE CANDIDATE ────────────────────────────────────────────────────────────
st.divider()
st.subheader("Move Candidate Between Stages")

all_flat = [c for stage_list in by_stage.values() for c in stage_list]
if all_flat:
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        opts = {f"{c['name']} ({c['stage']}) — {c['phone']}": c["id"] for c in all_flat}
        selected = st.selectbox("Candidate", list(opts.keys()), label_visibility="collapsed")
    with col2:
        new_stage = st.selectbox("New Stage", STAGES, label_visibility="collapsed")
    with col3:
        if st.button("Move →", type="primary", use_container_width=True):
            update_candidate_stage(opts[selected], new_stage)
            st.success(f"Moved to {new_stage}!")
            st.rerun()
else:
    st.info("No candidates yet. Add some from the Candidates page.")
