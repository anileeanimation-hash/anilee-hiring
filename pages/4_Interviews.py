import streamlit as st
import sys
import os
from datetime import date, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import add_interview, get_all_interviews, update_interview_status, get_all_candidates

st.set_page_config(page_title="Interviews — Anilee Hiring", page_icon="📅", layout="wide")
st.title("📅 Interview Management")

STATUSES = ["Scheduled", "Completed - Hired", "Completed - Rejected", "No Show", "Cancelled"]
STATUS_COLORS = {
    "Scheduled": "#0D6EFD",
    "Completed - Hired": "#198754",
    "Completed - Rejected": "#DC3545",
    "No Show": "#FFC107",
    "Cancelled": "#6C757D",
}

tab1, tab2 = st.tabs(["All Interviews", "📅 Schedule New Interview"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — ALL INTERVIEWS
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    status_filter = st.selectbox("Filter by Status", ["All"] + STATUSES)
    interviews = get_all_interviews()

    if status_filter != "All":
        interviews = [iv for iv in interviews if iv["status"] == status_filter]

    # Summary counts
    total_iv = len(interviews)
    scheduled = sum(1 for iv in interviews if iv["status"] == "Scheduled")
    hired = sum(1 for iv in interviews if iv["status"] == "Completed - Hired")

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Interviews", total_iv)
    m2.metric("Upcoming / Scheduled", scheduled)
    m3.metric("Hired After Interview", hired)

    st.divider()

    if not interviews:
        st.info("No interviews found. Schedule one using the next tab.")
    else:
        for iv in interviews:
            color = STATUS_COLORS.get(iv["status"], "#6C757D")
            with st.expander(
                f"**{iv['candidate_name']}** — {iv['scheduled_date']} at {iv['scheduled_time']} "
                f"| {iv['status']}"
            ):
                dc1, dc2, dc3 = st.columns([2, 2, 2])

                with dc1:
                    st.markdown(f"**Candidate:** {iv['candidate_name']}")
                    st.markdown(f"**Phone:** {iv['candidate_phone']}")
                    st.markdown(f"**Date:** {iv['scheduled_date']}")
                    st.markdown(f"**Time:** {iv['scheduled_time']}")

                with dc2:
                    st.markdown(f"**Interviewer:** {iv['interviewer']}")
                    st.markdown(f"**Duration:** {iv['duration_minutes']} mins")
                    st.markdown(f"**Mode:** {iv['mode']}")
                    st.markdown(f"**Scheduled on:** {iv['created_at'][:16]}")

                with dc3:
                    st.markdown(
                        f"<div style='background:{color};color:white;padding:6px 12px;"
                        f"border-radius:8px;text-align:center;font-weight:600;"
                        f"margin-bottom:10px;'>{iv['status']}</div>",
                        unsafe_allow_html=True
                    )
                    new_status = st.selectbox(
                        "Update Status", STATUSES,
                        index=STATUSES.index(iv["status"]) if iv["status"] in STATUSES else 0,
                        key=f"ivs_{iv['id']}"
                    )
                    new_notes = st.text_input("Notes", value=iv.get("notes", ""),
                                             key=f"ivn_{iv['id']}")
                    if st.button("Save", key=f"ivsave_{iv['id']}", type="primary"):
                        update_interview_status(iv["id"], new_status, new_notes)
                        st.success("Updated!")
                        st.rerun()

                if iv.get("notes") and not st.session_state.get(f"ivn_{iv['id']}"):
                    st.caption(f"Notes: {iv['notes']}")

                # WhatsApp reminder helper
                with st.expander("📱 Generate WhatsApp Reminder"):
                    reminder = f"""Namaste {iv['candidate_name']}! 🙏

Aapla *Anilee Academy* madhe interview confirm aahe:
📅 Date: {iv['scheduled_date']}
⏰ Time: {iv['scheduled_time']}
📍 Mode: {iv['mode']}
👤 Interviewer: {iv['interviewer']}

Please vel var ya. Kahi question asel tar call kara.

— HR Team, Anilee Academy"""
                    st.text_area("Message", reminder, height=200, key=f"reminder_{iv['id']}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SCHEDULE NEW INTERVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Schedule a New Interview")

    all_cands = get_all_candidates()
    eligible = [c for c in all_cands
                if c["stage"] not in ["Hired", "Rejected"] or
                c.get("score_band") in ["Hot 🔥", "Warm ✅"]]

    if not eligible:
        st.info("No eligible candidates found. Screen some candidates first.")
    else:
        with st.form("sched_form"):
            sf1, sf2 = st.columns(2)

            with sf1:
                cand_opts = {
                    f"{c['name']} — {c['stage']} | Score: {c.get('score', 0)}% "
                    f"| {c.get('score_band', 'Unscored')} | 📱 {c['phone']}": c
                    for c in eligible
                }
                selected_label = st.selectbox("Select Candidate *", list(cand_opts.keys()))
                selected_cand = cand_opts[selected_label]

                iv_date = st.date_input("Interview Date *", min_value=date.today(),
                                        value=date.today())
                iv_time = st.time_input("Interview Time *", value=time(10, 0))
                interviewer = st.text_input("Interviewer Name", value="HR Manager")

            with sf2:
                duration = st.selectbox("Duration", [30, 45, 60, 90], index=0,
                                       format_func=lambda x: f"{x} minutes")
                mode = st.selectbox("Interview Mode",
                                   ["In Person", "Video Call (Google Meet)", "Phone Call"])
                notes = st.text_area("Notes for Interviewer",
                                    placeholder="Key points to cover, candidate background…",
                                    height=100)

            if st.form_submit_button("📅 Schedule Interview", type="primary", use_container_width=True):
                add_interview(
                    candidate_id=selected_cand["id"],
                    candidate_name=selected_cand["name"],
                    candidate_phone=selected_cand.get("phone", ""),
                    scheduled_date=iv_date.strftime("%Y-%m-%d"),
                    scheduled_time=iv_time.strftime("%H:%M"),
                    duration_minutes=int(duration),
                    interviewer=interviewer,
                    mode=mode,
                    notes=notes
                )
                st.success(
                    f"✅ Interview scheduled for **{selected_cand['name']}** "
                    f"on {iv_date.strftime('%d %b %Y')} at {iv_time.strftime('%I:%M %p')}!"
                )
                st.info(f"📱 Candidate Phone: **{selected_cand.get('phone', 'N/A')}**  \n"
                        f"Remember to send a WhatsApp confirmation message.")
                st.balloons()
