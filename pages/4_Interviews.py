import streamlit as st
import sys
import os
from datetime import date, time, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import (add_interview, get_all_interviews, update_interview_status,
                      get_all_candidates, get_candidate, log_activity)

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


def _send_invite(candidate_name, candidate_email, iv_date_str, iv_time_str, mode, interviewer, candidate_id, meet_link=""):
    """Send interview invite email and return (ok, message)."""
    try:
        from utils.email_service import send_interview_invite
        ok, msg = send_interview_invite(
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            interview_date=datetime.strptime(iv_date_str, "%Y-%m-%d").strftime("%d %B %Y"),
            interview_time=iv_time_str + " IST",
            meet_link=meet_link,
            interviewer=interviewer,
            mode=mode
        )
        if ok:
            log_activity(candidate_id, candidate_name, "Interview Email Sent",
                         f"Invite sent to {candidate_email}", "System")
        return ok, msg
    except Exception as e:
        return False, str(e)


tab1, tab2 = st.tabs(["All Interviews", "📅 Schedule New Interview"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — ALL INTERVIEWS
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    status_filter = st.selectbox("Filter by Status", ["All"] + STATUSES)
    interviews = get_all_interviews()

    if status_filter != "All":
        interviews = [iv for iv in interviews if iv["status"] == status_filter]

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

                # ── Resend Interview Email ────────────────────────────────────
                cand = get_candidate(iv["candidate_id"])
                cand_email = cand.get("email", "") if cand else ""
                if cand_email:
                    if st.button(f"📧 Resend Interview Email", key=f"resend_{iv['id']}"):
                        # Extract meet link from notes if present
                        import re as _re
                        ml_match = _re.search(r'(https://meet\.google\.com/\S+)', iv.get("notes", ""))
                        ml = ml_match.group(1) if ml_match else ""
                        ok, msg = _send_invite(
                            iv["candidate_name"], cand_email,
                            iv["scheduled_date"], iv["scheduled_time"],
                            iv["mode"], iv["interviewer"], iv["candidate_id"], ml
                        )
                        if ok:
                            st.success(f"✅ Interview email resent to {cand_email}")
                        else:
                            st.error(f"❌ Failed: {msg}")
                else:
                    st.warning("⚠️ No email on file — cannot send invite")

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
    eligible = [c for c in all_cands if c["stage"] not in ["Hired", "Rejected"]]

    if not eligible:
        st.info("No candidates found. Add a candidate from the Candidates page first.")
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
                send_email_flag = st.checkbox("📧 Send interview invite email to candidate", value=True)

            if st.form_submit_button("📅 Schedule Interview", type="primary", use_container_width=True):
                if not interviewer.strip():
                    st.error("⚠️ Please enter the interviewer name.")
                else:
                    try:
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

                        # Auto-send interview invite email
                        cand_email = selected_cand.get("email", "")
                        if send_email_flag and cand_email:
                            ok, msg = _send_invite(
                                selected_cand["name"], cand_email,
                                iv_date.strftime("%Y-%m-%d"), iv_time.strftime("%H:%M"),
                                mode, interviewer, selected_cand["id"], meet_link=""
                            )
                            if ok:
                                st.success(f"📧 Interview invite email sent to **{cand_email}**")
                            else:
                                st.warning(f"⚠️ Interview saved but email failed: {msg}")
                        elif send_email_flag and not cand_email:
                            st.warning("⚠️ No email on file for this candidate — invite not sent. "
                                       "Add their email from the Candidates page.")

                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Could not save interview: {e}")
