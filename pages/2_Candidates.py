import streamlit as st
import sys
import os
import threading
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import (get_all_candidates, add_candidate, update_candidate_stage,
                       delete_candidate, get_candidate_responses, save_response,
                       update_candidate_score, get_screening_questions,
                       import_candidates_from_csv, log_activity, get_activity_log,
                       save_resume, get_resume, delete_resume,
                       STAGES, SOURCES)
from utils.ai_screener import score_response, evaluate_full_screening


def _send_screening_email_async(candidate_id: int, name: str, email: str):
    """Fire-and-forget: send screening email in background so UI doesn't block."""
    def _worker():
        try:
            from utils.db import get_screening_questions, update_candidate_stage, log_activity, get_activity_log
            from utils.email_service import send_screening_email
            # Only send if not already sent
            activity = get_activity_log(candidate_id, limit=20)
            already_sent = any(a["action"] == "Screening Email Sent" for a in activity)
            if already_sent:
                return
            questions = get_screening_questions(enabled_only=True)
            ok, msg = send_screening_email(name, email, questions, candidate_id)
            if ok:
                update_candidate_stage(candidate_id, "Outreached", "System")
                log_activity(candidate_id, name, "Screening Email Sent",
                             f"Auto-sent to {email}", "System")
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

st.set_page_config(page_title="Candidates — Anilee Hiring", page_icon="👥", layout="wide")
st.title("👥 Candidates")

tab1, tab2, tab3 = st.tabs(["All Candidates", "➕ Add New", "📥 Import CSV"])

BAND_COLORS = {
    "Hot 🔥": "#DC3545", "Warm ✅": "#198754",
    "Cold ❄️": "#0D6EFD", "Rejected ❌": "#6C757D", "Unscored": "#ADB5BD",
}

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — ALL CANDIDATES
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    cf1, cf2, cf3, cf4 = st.columns(4)
    with cf1:
        search = st.text_input("🔍 Search name / phone", placeholder="Ramesh…")
    with cf2:
        stage_f = st.selectbox("Stage", ["All"] + STAGES)
    with cf3:
        band_f = st.selectbox("Score Band", ["All", "Hot 🔥", "Warm ✅", "Cold ❄️", "Rejected ❌", "Unscored"])
    with cf4:
        source_f = st.selectbox("Source", ["All"] + SOURCES)

    candidates = get_all_candidates(
        stage_filter=stage_f if stage_f != "All" else None,
        band_filter=band_f if band_f != "All" else None,
        source_filter=source_f if source_f != "All" else None,
        search=search.strip() if search else None,
    )

    st.caption(f"Showing **{len(candidates)}** candidates")

    if not candidates:
        st.info("No candidates found. Use 'Add New' or 'Import CSV' tab to get started.")
    else:
        for cand in candidates:
            band = cand.get("score_band") or "Unscored"
            bc = BAND_COLORS.get(band, "#ADB5BD")
            score_display = f"{cand['score']}%" if cand.get("score", 0) > 0 else "Not screened"
            label = f"**{cand['name']}** — {cand['stage']} | {band} | 📱 {cand['phone']}"

            with st.expander(label):
                dc1, dc2, dc3 = st.columns([2, 2, 1.5])

                with dc1:
                    st.markdown(f"**Phone:** {cand['phone']}")
                    st.markdown(f"**Email:** {cand.get('email') or '—'}")
                    st.markdown(f"**Source:** {cand['source']}")
                    st.markdown(f"**Location:** {cand.get('location') or 'Satara'}")
                    st.markdown(f"**Added:** {cand['created_at'][:16]}")

                with dc2:
                    st.markdown(f"**Stage:** {cand['stage']}")
                    st.markdown(f"**Score:** {score_display}  "
                                f"<span style='background:{bc};color:white;padding:2px 8px;"
                                f"border-radius:10px;font-size:12px;'>{band}</span>",
                                unsafe_allow_html=True)
                    st.markdown(f"**Experience:** {cand.get('experience_months', 0)} months")
                    st.markdown(f"**Expected Salary:** ₹{int(cand.get('expected_salary', 0)):,}")

                with dc3:
                    cur_idx = STAGES.index(cand["stage"]) if cand["stage"] in STAGES else 0
                    new_stage = st.selectbox("Change Stage", STAGES, index=cur_idx,
                                             key=f"stg_{cand['id']}")
                    if st.button("Update Stage", key=f"upd_{cand['id']}"):
                        update_candidate_stage(cand["id"], new_stage)
                        st.success("Updated!")
                        st.rerun()

                if cand.get("notes"):
                    st.caption(f"Notes: {cand['notes']}")

                if cand.get("ai_summary"):
                    st.info(f"**AI Summary:** {cand['ai_summary']}")

                # ── RESUME SECTION ────────────────────────────────────────────
                st.markdown("---")
                resume_col1, resume_col2 = st.columns([3, 1])
                with resume_col1:
                    st.markdown("**📎 Resume**")
                with resume_col2:
                    show_resume_key = f"show_resume_{cand['id']}"
                    if st.button("⬆️ Upload / Change", key=f"res_toggle_{cand['id']}", use_container_width=True):
                        st.session_state[show_resume_key] = not st.session_state.get(show_resume_key, False)

                # Show existing resume
                res_path, res_bytes = get_resume(cand["id"])
                if res_bytes:
                    res_filename = os.path.basename(res_path) if res_path else "resume"
                    ext = os.path.splitext(res_filename)[1].lower()
                    dl_name = f"{cand['name'].replace(' ','_')}_resume{ext}"
                    r1, r2 = st.columns(2)
                    with r1:
                        st.download_button(
                            label=f"⬇️ Download Resume",
                            data=res_bytes,
                            file_name=dl_name,
                            mime="application/pdf" if ext == ".pdf" else "application/octet-stream",
                            key=f"dl_res_{cand['id']}",
                            use_container_width=True
                        )
                    with r2:
                        if st.button("🗑️ Remove Resume", key=f"del_res_{cand['id']}", use_container_width=True):
                            delete_resume(cand["id"])
                            st.success("Resume removed.")
                            st.rerun()
                elif res_path and not res_bytes:
                    st.caption("⚠️ Resume file was lost on server restart. Please re-upload.")
                else:
                    st.caption("No resume uploaded yet.")

                # Upload form
                if st.session_state.get(show_resume_key):
                    uploaded_resume = st.file_uploader(
                        "Upload Resume (PDF or Word)",
                        type=["pdf", "docx", "doc"],
                        key=f"res_upload_{cand['id']}"
                    )
                    if uploaded_resume:
                        if st.button("✅ Save Resume", key=f"res_save_{cand['id']}", type="primary"):
                            save_resume(cand["id"], uploaded_resume.name, uploaded_resume.read())
                            st.success(f"✅ Resume saved for **{cand['name']}**!")
                            st.session_state[show_resume_key] = False
                            st.rerun()

                st.markdown("---")

                # Action buttons
                ab1, ab2 = st.columns(2)
                with ab1:
                    if st.button("🤖 Run AI Screening", key=f"scr_{cand['id']}", type="primary"):
                        st.session_state[f"show_screen_{cand['id']}"] = True
                with ab2:
                    if st.button("🗑️ Delete Candidate", key=f"del_{cand['id']}"):
                        delete_candidate(cand["id"])
                        st.warning(f"Deleted {cand['name']}.")
                        st.rerun()

                # ── SCREENING PANEL ───────────────────────────────────────────
                if st.session_state.get(f"show_screen_{cand['id']}"):
                    st.markdown("---")
                    st.markdown("### 🤖 AI Screening Panel")
                    st.caption("Enter the candidate's verbal/call responses below. Claude AI will score them.")

                    questions = get_screening_questions(enabled_only=True)
                    if not questions:
                        st.warning("No questions enabled. Go to ⚙️ Screening Setup.")
                    else:
                        existing = {r["question_id"]: r["response"]
                                    for r in get_candidate_responses(cand["id"])}
                        resp_inputs = {}

                        hf_qs = [q for q in questions if q["is_hard_filter"]]
                        soft_qs = [q for q in questions if not q["is_hard_filter"]]

                        if hf_qs:
                            st.markdown("**🚨 Mandatory Qualification Checks**")
                            for q in hf_qs:
                                st.markdown(f"**{q['question']}**")
                                resp_inputs[q["id"]] = st.text_input(
                                    "Answer", value=existing.get(q["id"], ""),
                                    key=f"r_{cand['id']}_{q['id']}",
                                    placeholder="ho / yes / haa …",
                                    label_visibility="collapsed"
                                )

                        if soft_qs:
                            st.markdown("**📊 Scoring Questions**")
                            for q in soft_qs:
                                st.markdown(f"**Q: {q['question']}**")
                                st.caption(f"Category: {q['category']}  |  Weight: {q['weight']}")
                                resp_inputs[q["id"]] = st.text_area(
                                    "Answer", value=existing.get(q["id"], ""),
                                    key=f"r_{cand['id']}_{q['id']}",
                                    height=75, label_visibility="collapsed"
                                )

                        col_run, col_cancel = st.columns(2)
                        with col_cancel:
                            if st.button("Cancel", key=f"cancel_{cand['id']}"):
                                del st.session_state[f"show_screen_{cand['id']}"]
                                st.rerun()

                        with col_run:
                            if st.button("🚀 Score with AI", key=f"score_{cand['id']}", type="primary"):
                                has_any_response = any(v.strip() for v in resp_inputs.values())
                                if not has_any_response:
                                    st.warning("Please fill in at least some responses.")
                                else:
                                    with st.spinner("Claude is evaluating responses…"):
                                        scored_responses = []
                                        progress = st.progress(0)

                                        for idx, q in enumerate(questions):
                                            resp_text = resp_inputs.get(q["id"], "").strip()
                                            if resp_text:
                                                ai_score, ai_feedback = score_response(
                                                    q["question"], resp_text,
                                                    q["category"], q["is_hard_filter"], q["weight"]
                                                )
                                                save_response(cand["id"], q["id"], q["question"],
                                                              resp_text, ai_score, ai_feedback)
                                                scored_responses.append({
                                                    "question": q["question"],
                                                    "response": resp_text,
                                                    "category": q["category"],
                                                    "is_hard_filter": q["is_hard_filter"],
                                                    "weight": q["weight"],
                                                    "ai_score": ai_score,
                                                    "ai_feedback": ai_feedback,
                                                })
                                            progress.progress((idx + 1) / len(questions))

                                        if scored_responses:
                                            final_score, score_band, summary, failed = \
                                                evaluate_full_screening(cand["name"], scored_responses)
                                            update_candidate_score(cand["id"], final_score,
                                                                   score_band, summary)
                                            if cand["stage"] in ["New", "Outreached", "Screening"]:
                                                update_candidate_stage(cand["id"], "Screened", "AI System")

                                            if failed:
                                                st.error("❌ Failed hard filter — auto-rejected.")
                                            else:
                                                st.success(f"Score: **{final_score}%** — **{score_band}**")
                                            st.info(summary)

                                            del st.session_state[f"show_screen_{cand['id']}"]
                                            st.rerun()

                # ── PREVIOUS RESPONSES ────────────────────────────────────────
                responses = get_candidate_responses(cand["id"])
                if responses and not st.session_state.get(f"show_screen_{cand['id']}"):
                    with st.expander("📋 View Screening Responses"):
                        for r in responses:
                            if r.get("response"):
                                s = r.get("ai_score", 0)
                                sc = "#198754" if s >= 7 else ("#FFC107" if s >= 4 else "#DC3545")
                                st.markdown(f"""
                                <div style="padding:8px 10px; margin:4px 0; background:#f8f9fa;
                                            border-radius:6px; font-size:13px;">
                                    <b>Q: {r['question_text']}</b><br>
                                    A: {r['response']}<br>
                                    <span style="color:{sc};font-weight:600;">
                                        Score: {s}/10
                                    </span>
                                    {' — ' + r['ai_feedback'] if r['ai_feedback'] else ''}
                                </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ADD NEW CANDIDATE
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Add New Candidate Manually")
    with st.form("add_form", clear_on_submit=True):
        ac1, ac2 = st.columns(2)
        with ac1:
            name = st.text_input("Full Name *", placeholder="Ramesh Patil")
            phone = st.text_input("Phone Number *", placeholder="9876543210")
            email = st.text_input("Email", placeholder="candidate@email.com")
            source = st.selectbox("How did they apply?", SOURCES)
        with ac2:
            location = st.text_input("Location", value="Satara")
            experience_months = st.number_input("Experience (months)", 0, 120, 6)
            expected_salary = st.number_input("Expected Salary (₹)", 0, 100000, 18000, step=500)
            notes = st.text_area("Notes", placeholder="Any notes…", height=80)

        if st.form_submit_button("Add Candidate ➕", type="primary", use_container_width=True):
            if not name.strip() or not phone.strip():
                st.error("Name and phone are required.")
            else:
                cid = add_candidate(
                    name=name.strip(), phone=phone.strip(), email=email.strip(),
                    source=source, location=location.strip(),
                    experience_months=int(experience_months),
                    expected_salary=int(expected_salary), notes=notes.strip()
                )
                st.success(f"✅ {name.strip()} added to pipeline!")

                # Auto-send screening email immediately if email is provided
                if email.strip():
                    _send_screening_email_async(cid, name.strip(), email.strip())
                    st.info(f"📧 Screening email is being sent to **{email.strip()}** automatically.")
                else:
                    st.warning("⚠️ No email provided — screening email not sent. Add email to send manually via Automation page.")

                st.balloons()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — IMPORT CSV
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Import Candidates from CSV")
    st.info("Columns: **name, phone, email, source, location, experience_months, expected_salary, notes**  \n"
            "Only `name` and `phone` are required.")

    template_df = pd.DataFrame({
        "name": ["Ramesh Patil", "Priya Kadam"],
        "phone": ["9876543210", "9876543211"],
        "email": ["ramesh@email.com", "priya@email.com"],
        "source": ["Work India", "Apna"],
        "location": ["Satara", "Satara"],
        "experience_months": [6, 12],
        "expected_salary": [18000, 22000],
        "notes": ["Applied via app", ""],
    })
    st.download_button("📥 Download Template CSV", template_df.to_csv(index=False),
                       "import_template.csv", "text/csv")

    uploaded = st.file_uploader("Upload your CSV", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        st.dataframe(df.head(10), use_container_width=True)
        st.caption(f"Found {len(df)} rows")
        if st.button("Import All", type="primary"):
            added, errors = import_candidates_from_csv(df.to_dict("records"))
            st.success(f"✅ Imported {added} candidates!")
            if errors:
                for err in errors[:5]:
                    st.error(err)
            # Auto-send screening emails to all imported candidates with emails
            fresh_candidates = get_all_candidates(stage_filter="New")
            email_count = 0
            for c in fresh_candidates:
                if c.get("email"):
                    _send_screening_email_async(c["id"], c["name"], c["email"])
                    email_count += 1
            if email_count:
                st.info(f"📧 Sending screening emails to {email_count} candidates automatically.")
