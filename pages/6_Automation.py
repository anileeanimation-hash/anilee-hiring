"""
Automation Control Panel — HR can trigger, monitor and override the automation.
"""
import streamlit as st
import sys
import os
import json
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import (get_all_candidates, get_candidate, update_candidate_stage,
                       get_screening_questions, log_activity, get_activity_log, STAGES)
from utils.email_service import send_screening_email, send_interview_invite, send_hr_notification, is_gmail_setup
from utils.meet_scheduler import create_meet_event, is_calendar_setup
from utils.ai_screener import _get_api_key, _find_claude_binary

st.set_page_config(page_title="Automation — Anilee Hiring", page_icon="🤖", layout="wide")
st.title("🤖 Automation Control Panel")
st.caption("Monitor and control the full hiring automation pipeline")

# ── STATUS INDICATORS ─────────────────────────────────────────────────────────
st.subheader("System Status")
s1, s2, s3, s4 = st.columns(4)

# Check Claude CLI (search known paths)
try:
    binary = _find_claude_binary()
    r = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5)
    claude_ok = r.returncode == 0
except Exception:
    claude_ok = False

# Check API key
api_key = _get_api_key()

# Check Gmail (OAuth2)
gmail_ok = is_gmail_setup()

# Check Google Calendar
gcal_ok = is_calendar_setup()

with s1:
    if claude_ok or api_key:
        st.success("🤖 Claude AI: Ready")
    else:
        st.error("🤖 Claude AI: Not configured")

with s2:
    if gmail_ok:
        st.success("📧 Gmail: Connected")
    else:
        st.warning("📧 Gmail: Setup needed")

with s3:
    if gcal_ok:
        st.success("📅 Google Meet: Ready")
    else:
        st.warning("📅 Google Meet: Setup needed")

with s4:
    st.info("🔄 Worker: Manual / Scheduled")

st.divider()

# ── AUTOMATION PIPELINE ────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚀 Run Automation", "📧 Email Actions", "📅 Schedule Interview", "🔍 Indeed Sourcer", "⚙️ Setup Guide"
])

# TAB 1: RUN AUTOMATION
with tab1:
    st.subheader("Full Automation Cycle")
    st.info("""
    **What this does automatically:**
    1. Sends screening emails to all new candidates (who have email)
    2. Reads candidate email replies
    3. Scores them with Claude AI
    4. Moves to correct stage (Screened / Rejected)
    5. Auto-schedules Google Meet for Hot 🔥 candidates
    6. Sends interview invites + notifies HR
    """)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Run Full Automation Now", type="primary", use_container_width=True):
            with st.spinner("Running automation cycle..."):
                try:
                    # Run directly in-process so st.secrets and venv packages are available
                    from automation.worker import run_full_cycle
                    data = run_full_cycle()
                    st.success("✅ Automation cycle completed!")
                    st.metric("Emails Sent", data.get("emails_sent", 0))
                    st.metric("Replies Processed", data.get("replies_processed", 0))
                    st.json(data)
                except Exception as e:
                    st.error(f"Automation error: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    with col2:
        st.subheader("Set Auto Schedule")
        interval = st.selectbox("Run every", ["30 minutes", "1 hour", "2 hours", "4 hours"])
        if st.button("Enable Auto-Run", use_container_width=True):
            interval_map = {"30 minutes": 30, "1 hour": 60, "2 hours": 120, "4 hours": 240}
            mins = interval_map[interval]
            cron = f"*/{mins} * * * *" if mins < 60 else f"0 */{mins//60} * * *"
            worker_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "automation/worker.py")
            cron_line = f'{cron} python3 {worker_path} >> /tmp/hiring-worker.log 2>&1'
            try:
                result = subprocess.run(
                    f'(crontab -l 2>/dev/null | grep -v worker.py; echo "{cron_line}") | crontab -',
                    shell=True, capture_output=True, text=True
                )
                st.success(f"✅ Auto-run enabled every {interval}!")
                st.code(f"Cron: {cron_line}")
            except Exception as e:
                st.error(f"Failed: {e}")
                st.info("Manual alternative: Run the worker script whenever needed.")

    st.divider()
    st.subheader("Recent Worker Log")
    try:
        with open("/tmp/hiring-worker.log", "r") as f:
            lines = f.readlines()
            log_text = "".join(lines[-30:])
        st.code(log_text, language=None)
    except FileNotFoundError:
        st.info("No log yet. Run the automation above to start.")


# TAB 2: EMAIL ACTIONS
with tab2:
    st.subheader("Manual Email Actions")
    st.caption("Trigger emails manually for specific candidates")

    candidates = get_all_candidates()
    if not candidates:
        st.info("No candidates yet.")
    else:
        cand_opts = {f"{c['name']} — {c['stage']} | 📱 {c['phone']} | ✉️ {c.get('email','no email')}": c
                     for c in candidates}

        selected_label = st.selectbox("Select Candidate", list(cand_opts.keys()))
        selected = cand_opts[selected_label]

        if not selected.get("email"):
            st.warning("⚠️ This candidate has no email address. Add it in Candidates page first.")
        else:
            ec1, ec2, ec3 = st.columns(3)

            with ec1:
                if st.button("📤 Send Screening Email", use_container_width=True):
                    questions = get_screening_questions(enabled_only=True)
                    ok, msg = send_screening_email(
                        selected["name"], selected["email"], questions, selected["id"]
                    )
                    if ok:
                        update_candidate_stage(selected["id"], "Outreached", "HR")
                        log_activity(selected["id"], selected["name"],
                                    "Screening Email Sent", f"To: {selected['email']}", "HR")
                        st.success(f"✅ Sent to {selected['email']}")
                    else:
                        st.error(f"❌ {msg}")

            with ec2:
                if st.button("❌ Send Rejection Email", use_container_width=True):
                    ok, msg = send_rejection_email(selected["name"], selected["email"])
                    if ok:
                        update_candidate_stage(selected["id"], "Rejected", "HR")
                        log_activity(selected["id"], selected["name"],
                                    "Rejection Email Sent", f"To: {selected['email']}", "HR")
                        st.success("Rejection email sent.")
                    else:
                        st.error(f"❌ {msg}")

            with ec3:
                if st.button("🔔 Notify HR About Candidate", use_container_width=True):
                    ok, msg = send_hr_notification(
                        f"Candidate Update: {selected['name']}",
                        f"Name: {selected['name']}\nPhone: {selected.get('phone','N/A')}\n"
                        f"Stage: {selected['stage']}\nScore: {selected.get('score',0)}% {selected.get('score_band','')}\n"
                        f"Email: {selected.get('email','N/A')}\nNotes: {selected.get('notes','')}"
                    )
                    st.success("HR notified!" if ok else f"Failed: {msg}")

            # HR Override section
            st.divider()
            st.subheader("HR Override")
            st.caption("If automation rejected a good candidate, override here and continue the process.")
            override_stage = st.selectbox("Force move to stage", STAGES, key="override_stage")
            override_notes = st.text_input("Reason for override")
            if st.button("⚡ Override Stage", type="secondary"):
                update_candidate_stage(selected["id"], override_stage, "HR Override")
                log_activity(selected["id"], selected["name"],
                            "HR Override", f"Forced to {override_stage}. Reason: {override_notes}", "HR")
                st.success(f"Moved to {override_stage}")
                st.rerun()


# TAB 3: SCHEDULE INTERVIEW
with tab3:
    st.subheader("Auto-Schedule Google Meet Interview")

    candidates = get_all_candidates()
    ready = [c for c in candidates if c["stage"] == "Screened" or c.get("score_band") == "Hot 🔥"]

    if not ready:
        st.info("No screened candidates ready for interview scheduling.")
    else:
        with st.form("auto_schedule_form"):
            af1, af2 = st.columns(2)
            with af1:
                opts = {f"{c['name']} — {c.get('score',0)}% {c.get('score_band','')} | {c.get('phone','')}": c
                        for c in ready}
                sel = st.selectbox("Candidate", list(opts.keys()))
                sel_cand = opts[sel]
                from datetime import date, time
                iv_date = st.date_input("Interview Date", min_value=date.today())
                iv_time = st.time_input("Time", value=time(10, 0))
            with af2:
                interviewer_email = st.text_input("Interviewer Email", value="hr.anileeanimation@gmail.com")
                duration = st.selectbox("Duration", [30, 45, 60], index=0, format_func=lambda x: f"{x} min")
                auto_send_invite = st.checkbox("Auto-send invite to candidate", value=True)
                auto_notify_hr = st.checkbox("Notify HR via email", value=True)

            if st.form_submit_button("📅 Create Meet & Schedule", type="primary", use_container_width=True):
                with st.spinner("Creating Google Meet..."):
                    meet_link, event_id, err = create_meet_event(
                        candidate_name=sel_cand["name"],
                        candidate_email=sel_cand.get("email", ""),
                        interview_date=iv_date.strftime("%Y-%m-%d"),
                        interview_time=iv_time.strftime("%H:%M"),
                        duration_minutes=duration,
                        interviewer_email=interviewer_email
                    )

                    from utils.db import add_interview
                    add_interview(
                        candidate_id=sel_cand["id"],
                        candidate_name=sel_cand["name"],
                        candidate_phone=sel_cand.get("phone", ""),
                        scheduled_date=iv_date.strftime("%Y-%m-%d"),
                        scheduled_time=iv_time.strftime("%H:%M"),
                        duration_minutes=duration,
                        interviewer="HR",
                        mode="Google Meet",
                        notes=f"Meet: {meet_link}"
                    )

                    if auto_send_invite and sel_cand.get("email"):
                        send_interview_invite(
                            candidate_name=sel_cand["name"],
                            candidate_email=sel_cand["email"],
                            interview_date=iv_date.strftime("%d %B %Y"),
                            interview_time=iv_time.strftime("%I:%M %p") + " IST",
                            meet_link=meet_link
                        )

                    if auto_notify_hr:
                        send_hr_notification(
                            f"Interview Scheduled: {sel_cand['name']}",
                            f"Candidate: {sel_cand['name']}\nDate: {iv_date}\nTime: {iv_time}\nMeet: {meet_link}"
                        )

                    st.success(f"✅ Interview scheduled!")
                    st.markdown(f"**Google Meet Link:** [{meet_link}]({meet_link})")
                    if err:
                        st.warning(f"Note: {err} — Used generated link instead.")
                    st.balloons()


# TAB 4: INDEED SOURCER
with tab4:
    st.subheader("🔍 Indeed Candidate Sourcer")
    st.caption("Auto-imports candidates from your Indeed job postings (FREE — no paid plan needed)")

    st.info("""
    **How it works:**
    - Candidates who apply to your Indeed job posting have their **full CV visible for free**
    - This sourcer reads those applicants, adds them to the portal, and sends screening emails
    - Runs de-duplication — existing candidates are never added twice
    - **15 candidates** scraped from Indeed (2026-03-24) are ready to import
    """)

    from utils.db import get_all_candidates as _get_all
    from automation.indeed_sourcer import INDEED_CANDIDATES, run_import, is_duplicate, _existing_phones_emails

    # Show pending vs already imported
    existing_phones, existing_emails = _existing_phones_emails()
    pending = [c for c in INDEED_CANDIDATES if not is_duplicate(c, existing_phones, existing_emails)]
    already_imported = [c for c in INDEED_CANDIDATES if is_duplicate(c, existing_phones, existing_emails)]

    m1, m2, m3 = st.columns(3)
    m1.metric("Total scraped from Indeed", len(INDEED_CANDIDATES))
    m2.metric("Already in portal", len(already_imported))
    m3.metric("Ready to import", len(pending), delta=f"+{len(pending)} new" if pending else None)

    st.divider()

    if pending:
        st.subheader(f"📥 {len(pending)} New Candidates to Import")

        # Preview table
        import pandas as pd
        preview_data = []
        for c in pending:
            preview_data.append({
                "Name": c["name"],
                "Phone": c["phone"],
                "Email": c["email"],
                "Location": c["location"],
                "Role Applied": c.get("job_role", ""),
                "Experience": f"{c.get('experience_months', 0) // 12}yr {c.get('experience_months', 0) % 12}mo" if c.get("experience_months") else "Fresh",
            })
        st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)

        col_a, col_b = st.columns(2)
        with col_a:
            send_emails_toggle = st.checkbox("📧 Auto-send screening email to each", value=False,
                                              help="Sends screening form link via Gmail to each new candidate")
        with col_b:
            st.write("")

        if st.button("▶️ Import Now", type="primary", use_container_width=True):
            with st.spinner(f"Importing {len(pending)} candidates…"):
                result = run_import(send_emails=send_emails_toggle)

            if result["added"] > 0:
                st.success(f"✅ Imported {result['added']} candidates! "
                           f"{'📧 Screening emails queued.' if result['email_queued'] else ''}")
            else:
                st.info("No new candidates added (all already in portal).")

            c1, c2, c3 = st.columns(3)
            c1.metric("Added", result["added"])
            c2.metric("Duplicates skipped", result["skipped_duplicates"])
            c3.metric("Emails sent", result["email_queued"])

            if result["errors"]:
                st.error("Errors:\n" + "\n".join(result["errors"]))

            # Detail table
            detail_df = pd.DataFrame(result["details"])
            if not detail_df.empty:
                st.dataframe(detail_df, use_container_width=True, hide_index=True)

            st.rerun()

    else:
        st.success("✅ All 15 Indeed candidates are already in the portal!")

    if already_imported:
        with st.expander(f"Already imported ({len(already_imported)})"):
            for c in already_imported:
                st.write(f"• **{c['name']}** — {c['phone']} — {c['location']}")

    st.divider()
    st.subheader("🔄 How to Get Fresh Candidates from Indeed")
    st.markdown("""
    **Step 1:** Open [employers.indeed.com/candidates](https://employers.indeed.com/candidates) → your candidates appear here when someone applies.

    **Step 2:** When new applicants arrive, ask Claude to "scrape today's Indeed candidates" — it will visit each profile, extract contact info, and update `INDEED_CANDIDATES` in `automation/indeed_sourcer.py`.

    **Step 3:** Come back here and click **Import Now** — new ones added, duplicates skipped automatically.

    > 💡 **Tip:** Post more jobs on Indeed for free → more applicants → more free candidates daily.
    """)


# TAB 5: SETUP GUIDE
with tab5:
    st.subheader("⚙️ Setup Guide — Complete These Steps")

    with st.expander("1. 🤖 Claude AI (for screening) — REQUIRED", expanded=not (claude_ok or api_key)):
        st.markdown("""
        **Option A (Free — uses your Claude Code subscription):**
        Nothing to do! Claude CLI is already set up.

        **Option B (API Key — faster, independent):**
        1. Go to [console.anthropic.com](https://console.anthropic.com)
        2. Create account → Add $5 credit (lasts ~500 screenings)
        3. Create API key
        4. Add to `.streamlit/secrets.toml`:
        ```toml
        ANTHROPIC_API_KEY = "sk-ant-..."
        ```
        """)

    with st.expander("2. 📧 Gmail — OAuth2 Setup", expanded=not gmail_ok):
        st.markdown("""
        Gmail uses **OAuth2** (same token as Google Calendar — no App Password needed).

        ✅ **Already configured** if `token.pkl` exists in `hiring_portal/`.

        To re-authorize or set up fresh:
        ```bash
        cd ~/Documents/Claude/hiring_portal
        python3 utils/meet_scheduler.py --auth
        ```
        This opens a browser to authorize Gmail + Calendar access for `hr.anileeanimation@gmail.com`.
        """)

    with st.expander("3. 📅 Google Meet / Calendar — REQUIRED for auto-scheduling", expanded=not gcal_ok):
        st.markdown("""
        **Steps:**
        1. Go to [console.cloud.google.com](https://console.cloud.google.com)
        2. Create a new project (e.g., "Anilee Hiring")
        3. Enable **Google Calendar API**
        4. Go to **Credentials** → Create OAuth2 Client → Desktop App
        5. Download as `credentials.json`
        6. Place in: `/Users/shagunsalunkhe/Documents/Claude/hiring_portal/credentials.json`
        7. Run once to authorize:
        ```bash
        cd ~/Documents/Claude/hiring_portal
        python3 utils/meet_scheduler.py --auth
        ```
        (Opens browser, sign in with hr.anileeanimation@gmail.com, allow access)
        """)

    with st.expander("4. 🌐 Public URL (so HR can access from any PC) — REQUIRED", expanded=True):
        st.markdown("""
        The Cloudflare Tunnel gives your HR a permanent public URL.

        **Steps:**
        1. Create a free account at [cloudflare.com](https://cloudflare.com)
        2. Open Terminal and run:
        ```bash
        ~/cloudflared tunnel --url http://localhost:8503
        ```
        3. You'll see a URL like: `https://hiring-anilee.trycloudflare.com`
        4. Share that URL with your HR — they can open it from any computer!

        For a **permanent URL** (doesn't change on restart):
        - Register a free domain from Cloudflare
        - Set up a named tunnel (I can help with this)
        """)

    with st.expander("5. 📱 WhatsApp Automation (optional — for WhatsApp outreach)"):
        st.markdown("""
        Currently system uses email. To add WhatsApp:
        1. Create a free account at [wati.io](https://wati.io) or [aisensy.com](https://aisensy.com)
        2. Connect your WhatsApp Business number
        3. Get API credentials
        4. I'll add WhatsApp integration once email automation is confirmed working

        **For now:** Use the WhatsApp template from ⚙️ Screening Setup page — copy and paste manually.
        """)
