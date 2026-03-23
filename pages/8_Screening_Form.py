"""
Candidate Screening Form — public-facing page.
Candidate clicks the link in their email, fills this form, submits.
Claude AI scores instantly. No email Q&A needed.

URL: http://localhost:8503/Screening_Form?cid=3&token=abc123
"""
import streamlit as st
import sys, os, hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import (get_candidate, get_screening_questions, save_response,
                       update_candidate_score, update_candidate_stage, log_activity,
                       add_interview, get_connection)
from utils.ai_screener import score_email_reply
from utils.meet_scheduler import create_meet_event
from utils.email_service import send_interview_invite, send_hr_notification

st.set_page_config(
    page_title="Screening Form — Anilee Academy",
    page_icon="🎓",
    layout="centered"
)

# ── Hide sidebar & Streamlit chrome for public form ──────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { display: none; }
[data-testid="stHeader"]  { display: none; }
footer { display: none; }
.block-container { max-width: 680px; padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ── Read query params ─────────────────────────────────────────────────────────
params   = st.query_params
cid_str  = params.get("cid", "")
token    = params.get("token", "")

def _make_token(cid: int) -> str:
    secret = "anilee2026"
    return hashlib.md5(f"{cid}-{secret}".encode()).hexdigest()[:12]

# ── Validate ──────────────────────────────────────────────────────────────────
if not cid_str or not cid_str.isdigit():
    st.error("❌ Invalid link. Please use the link from your email.")
    st.stop()

cid = int(cid_str)
candidate = get_candidate(cid)

if not candidate:
    st.error("❌ Candidate not found. Please contact hr.anileeanimation@gmail.com")
    st.stop()

if token != _make_token(cid):
    st.error("❌ Invalid or expired link. Please use the original link from your email.")
    st.stop()

# ── Already submitted? ────────────────────────────────────────────────────────
if candidate["stage"] in ["Screened", "Interview Scheduled", "Hired", "Rejected"]:
    st.markdown("""
    <div style='text-align:center;padding:40px 0;'>
      <div style='font-size:64px;'>✅</div>
      <h2>Already Submitted!</h2>
      <p style='color:#555;'>We have already received your screening answers.<br>
      Our HR team will contact you shortly.</p>
      <p style='color:#888;font-size:14px;'>Questions? Email: hr.anileeanimation@gmail.com</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Load questions ────────────────────────────────────────────────────────────
questions = get_screening_questions(enabled_only=True)
if not questions:
    st.error("No screening questions configured. Please contact HR.")
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='background:#FF6B35;padding:24px 28px;border-radius:12px;margin-bottom:24px;'>
  <h2 style='color:white;margin:0;'>🎓 Anilee Academy, Satara</h2>
  <p style='color:rgba(255,255,255,0.9);margin:6px 0 0;font-size:15px;'>
    Educational Counsellor — Screening Form
  </p>
</div>
""", unsafe_allow_html=True)

st.markdown(f"**Namaste {candidate['name']}!** 👋")
st.markdown(
    "Please answer the questions below honestly. "
    "This takes about **3–5 minutes**. Your answers help us understand your profile better."
)
st.markdown("""
<div style='background:#fff8e1;border-left:4px solid #FFC107;padding:10px 14px;
            border-radius:4px;margin:12px 0 20px;font-size:13px;'>
  📌 <b>Salary Range:</b> ₹15,000 – ₹25,000/month &nbsp;|&nbsp;
  📍 <b>Location:</b> Satara, Maharashtra (In-office)
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Form ──────────────────────────────────────────────────────────────────────
with st.form("screening_form", clear_on_submit=False):
    answers = {}
    for i, q in enumerate(questions):
        st.markdown(f"**{i+1}. {q['question']}**")
        if q.get("question_type") == "yes_no":
            ans = st.radio(
                label=f"q_{q['id']}",
                options=["Yes", "No"],
                horizontal=True,
                label_visibility="collapsed",
                key=f"q_{q['id']}"
            )
        else:
            ans = st.text_area(
                label=f"q_{q['id']}",
                placeholder="Type your answer here...",
                height=80,
                label_visibility="collapsed",
                key=f"q_{q['id']}"
            )
        answers[q["id"]] = {"question": q["question"], "answer": ans}
        if i < len(questions) - 1:
            st.markdown("<div style='margin:8px 0;'></div>", unsafe_allow_html=True)

    st.divider()
    st.markdown("<div style='margin:4px 0 8px;'></div>", unsafe_allow_html=True)
    submitted = st.form_submit_button(
        "🚀 Submit My Answers",
        use_container_width=True,
        type="primary"
    )

# ── On Submit ─────────────────────────────────────────────────────────────────
if submitted:
    # Validate all answered
    empty = [i+1 for i, (qid, v) in enumerate(answers.items()) if not str(v["answer"]).strip()]
    if empty:
        st.warning(f"⚠️ Please answer question(s): {', '.join(map(str, empty))}")
        st.stop()

    with st.spinner("Saving your answers and analysing with AI... Please wait ⏳"):
        # Save individual answers to DB
        for qid, v in answers.items():
            save_response(cid, qid, v["question"], v["answer"])

        # Build combined text for Claude
        combined = "\n\n".join([
            f"{i+1}. {v['question']}\nAnswer: {v['answer']}"
            for i, (qid, v) in enumerate(answers.items())
        ])

        # Score with Claude AI
        score, band, summary, hard_fail = score_email_reply(
            candidate["name"], combined, questions
        )

        # Update DB
        update_candidate_score(cid, score, band, summary)

        if hard_fail:
            update_candidate_stage(cid, "Rejected", "AI System")
            log_activity(cid, candidate["name"], "Form Submitted + AI Scored",
                        f"{score}% {band} — Hard filter failed", "AI System")
        else:
            update_candidate_stage(cid, "Screened", "AI System")
            log_activity(cid, candidate["name"], "Form Submitted + AI Scored",
                        f"{score}% {band}", "AI System")

            # Auto-schedule Google Meet for Hot candidates
            if band == "Hot 🔥" and candidate.get("email"):
                _auto_schedule(cid, candidate, score)

    # ── Thank You Screen ──────────────────────────────────────────────────────
    if hard_fail:
        st.markdown("""
        <div style='text-align:center;padding:40px 20px;'>
          <div style='font-size:56px;'>🙏</div>
          <h2>Thank You for Applying!</h2>
          <p style='color:#555;max-width:480px;margin:0 auto;'>
            We have received your answers. After careful review, we will get back
            to you if your profile matches our current requirements.
          </p>
          <p style='color:#888;font-size:13px;margin-top:20px;'>
            Questions? Email: hr.anileeanimation@gmail.com
          </p>
        </div>
        """, unsafe_allow_html=True)
    elif band == "Hot 🔥":
        st.markdown(f"""
        <div style='text-align:center;padding:40px 20px;'>
          <div style='font-size:56px;'>🎉</div>
          <h2 style='color:#198754;'>Congratulations!</h2>
          <p style='color:#555;max-width:480px;margin:0 auto;'>
            Your profile is a <b>great match</b> for the Educational Counsellor position!
            We have scheduled a Google Meet interview for you.
            <b>Check your email for the interview details.</b>
          </p>
          <p style='color:#888;font-size:13px;margin-top:20px;'>
            Questions? Email: hr.anileeanimation@gmail.com
          </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='text-align:center;padding:40px 20px;'>
          <div style='font-size:56px;'>✅</div>
          <h2>Answers Submitted!</h2>
          <p style='color:#555;max-width:480px;margin:0 auto;'>
            Thank you <b>{candidate['name']}</b>! We have received your answers.
            Our HR team will review your profile and contact you within <b>2–3 working days</b>.
          </p>
          <p style='color:#888;font-size:13px;margin-top:20px;'>
            Questions? Email: hr.anileeanimation@gmail.com
          </p>
        </div>
        """, unsafe_allow_html=True)
    st.stop()


def _auto_schedule(cid, candidate, score):
    """Auto-schedule Google Meet for hot candidate after form submission."""
    from datetime import date, timedelta
    d = date.today() + timedelta(days=2)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    interview_date = d.strftime("%Y-%m-%d")

    meet_link, event_id, err = create_meet_event(
        candidate_name=candidate["name"],
        candidate_email=candidate.get("email", ""),
        interview_date=interview_date,
        interview_time="10:00",
        duration_minutes=30,
        interviewer_email="hr.anileeanimation@gmail.com",
        description=f"Screening Score: {score}% | Auto-scheduled via form"
    )
    if meet_link:
        add_interview(
            candidate_id=cid,
            candidate_name=candidate["name"],
            candidate_phone=candidate.get("phone", ""),
            scheduled_date=interview_date,
            scheduled_time="10:00",
            duration_minutes=30,
            interviewer="HR",
            mode="Google Meet",
            notes=f"Auto-scheduled via form. Score: {score}%. Meet: {meet_link}"
        )
        send_interview_invite(
            candidate_name=candidate["name"],
            candidate_email=candidate["email"],
            interview_date=d.strftime("%d %B %Y"),
            interview_time="10:00 AM IST",
            meet_link=meet_link,
            interviewer="HR Team"
        )
        send_hr_notification(
            subject=f"🔥 Hot Candidate Interview Auto-Scheduled — {candidate['name']}",
            body=f"Name: {candidate['name']}\nPhone: {candidate.get('phone','N/A')}\n"
                 f"Score: {score}%\nInterview: {interview_date} 10:00 AM\nMeet: {meet_link}"
        )
        update_candidate_stage(cid, "Interview Scheduled", "AI System")
        log_activity(cid, candidate["name"], "Interview Scheduled",
                    f"Auto via form. Meet: {meet_link}", "AI System")
