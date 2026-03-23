"""
Automation Worker — runs on a schedule, handles the full hiring pipeline automatically.

What it does every run:
1. Checks for new email replies from candidates
2. Scores replies with Claude AI
3. Moves candidates to correct stage
4. Auto-schedules Google Meet for Hot candidates
5. Sends interview invites
6. Sends rejection emails
7. Notifies HR of all actions

Run: python3 automation/worker.py
Or set up as a cron job (every 30 minutes)
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta, date, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import (
    get_all_candidates, get_candidate, update_candidate_stage,
    update_candidate_score, save_response, get_screening_questions,
    add_interview, log_activity, get_activity_log
)
from utils.email_service import (
    read_candidate_replies, send_screening_email,
    send_interview_invite, send_rejection_email, send_hr_notification
)
from utils.ai_screener import score_email_reply
from utils.meet_scheduler import create_meet_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/hiring-worker.log")
    ]
)
log = logging.getLogger("worker")


def process_email_replies():
    """Read candidate email replies and score them automatically."""
    log.info("Checking for new email replies...")
    replies = read_candidate_replies(since_hours=48)

    if not replies:
        log.info("No new replies found.")
        return 0

    log.info(f"Found {len(replies)} unread emails.")
    questions = get_screening_questions(enabled_only=True)
    processed = 0

    for reply in replies:
        candidate_id = reply.get("candidate_id")
        if not candidate_id:
            log.info(f"No candidate ID in email from {reply['from_email']} — skipping")
            continue

        candidate = get_candidate(candidate_id)
        if not candidate:
            log.warning(f"Candidate ID {candidate_id} not found in DB — skipping")
            continue

        if candidate["stage"] in ["Screened", "Interview Scheduled", "Hired", "Rejected"]:
            log.info(f"Candidate {candidate['name']} already past screening — skipping")
            continue

        log.info(f"Processing reply from {candidate['name']} (ID: {candidate_id})")

        # Score the email reply with Claude
        score, band, summary, hard_fail = score_email_reply(
            candidate["name"], reply["body"], questions
        )

        # Update database
        update_candidate_score(candidate_id, score, band, summary)

        if hard_fail:
            update_candidate_stage(candidate_id, "Rejected", "AI System")
            # Send rejection email if we have their email
            if candidate.get("email"):
                send_rejection_email(candidate["name"], candidate["email"])
                log.info(f"Rejected {candidate['name']} — hard filter failed. Rejection email sent.")
        else:
            update_candidate_stage(candidate_id, "Screened", "AI System")
            log.info(f"Scored {candidate['name']}: {score}% — {band}")

            # Auto-schedule interview for Hot candidates
            if band == "Hot 🔥":
                _auto_schedule_interview(candidate, score)

        log.activity = f"{candidate['name']}: {score}% {band}"
        processed += 1

    log.info(f"Processed {processed} replies.")
    return processed


def _auto_schedule_interview(candidate: dict, score: int):
    """Automatically schedule a Google Meet interview for Hot candidates."""
    log.info(f"Auto-scheduling interview for Hot candidate: {candidate['name']}")

    # Find next available weekday 2 days from now at 10am or 2pm
    interview_date = _next_available_date()
    interview_time = "10:00"

    # Create Google Meet
    meet_link, event_id, err = create_meet_event(
        candidate_name=candidate["name"],
        candidate_email=candidate.get("email", ""),
        interview_date=interview_date,
        interview_time=interview_time,
        duration_minutes=30,
        interviewer_email="hr.anileeanimation@gmail.com",
        description=f"Screening Score: {score}%\nCandidate Phone: {candidate.get('phone', 'N/A')}"
    )

    if err and not meet_link:
        log.error(f"Could not create Meet: {err}")
        return

    # Save to DB
    add_interview(
        candidate_id=candidate["id"],
        candidate_name=candidate["name"],
        candidate_phone=candidate.get("phone", ""),
        scheduled_date=interview_date,
        scheduled_time=interview_time,
        duration_minutes=30,
        interviewer="HR",
        mode="Google Meet",
        notes=f"Auto-scheduled. Score: {score}%. Meet: {meet_link}"
    )

    # Send invite to candidate
    if candidate.get("email"):
        ok, msg = send_interview_invite(
            candidate_name=candidate["name"],
            candidate_email=candidate["email"],
            interview_date=datetime.strptime(interview_date, "%Y-%m-%d").strftime("%d %B %Y"),
            interview_time=interview_time + " IST",
            meet_link=meet_link,
            interviewer="HR Team"
        )
        log.info(f"Interview invite sent to {candidate['name']}: {msg}")

    # Notify HR
    send_hr_notification(
        subject=f"🔥 Hot Candidate Interview Scheduled — {candidate['name']}",
        body=f"""Hot Candidate Auto-Scheduled for Interview

Name: {candidate['name']}
Phone: {candidate.get('phone', 'N/A')}
Email: {candidate.get('email', 'N/A')}
Screening Score: {score}%
Interview Date: {interview_date} at {interview_time}
Google Meet: {meet_link}

View on portal: http://localhost:8503/Interviews
"""
    )
    log.info(f"HR notified about {candidate['name']}'s interview.")


def send_pending_screening_emails():
    """Send screening emails to New candidates who haven't been contacted yet."""
    log.info("Checking for candidates who need screening emails...")
    candidates = get_all_candidates(stage_filter="New")
    questions = get_screening_questions(enabled_only=True)
    sent = 0

    for cand in candidates:
        if not cand.get("email"):
            continue

        # Check if already sent (look in activity log)
        activity = get_activity_log(cand["id"], limit=20)
        already_sent = any(a["action"] == "Screening Email Sent" for a in activity)

        if already_sent:
            continue

        ok, msg = send_screening_email(
            candidate_name=cand["name"],
            candidate_email=cand["email"],
            enabled_questions=questions,
            candidate_id=cand["id"]
        )

        if ok:
            update_candidate_stage(cand["id"], "Outreached", "AI System")
            log_activity(cand["id"], cand["name"], "Screening Email Sent",
                        f"Sent to {cand['email']}", "AI System")
            log.info(f"Screening email sent to {cand['name']}")
            sent += 1
        else:
            log.warning(f"Failed to send email to {cand['name']}: {msg}")

    log.info(f"Sent screening emails to {sent} candidates.")
    return sent


def _next_available_date(days_ahead: int = 2) -> str:
    """Get next available weekday for interview."""
    d = date.today() + timedelta(days=days_ahead)
    while d.weekday() >= 5:  # Skip weekend
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def run_full_cycle():
    """Run the complete automation cycle."""
    log.info("=" * 50)
    log.info(f"Automation cycle started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Step 1: Send screening emails to new candidates
    emails_sent = send_pending_screening_emails()

    # Step 2: Process email replies and score
    replies_processed = process_email_replies()

    log.info(f"Cycle complete. Emails sent: {emails_sent} | Replies processed: {replies_processed}")
    log.info("=" * 50)

    return {
        "emails_sent": emails_sent,
        "replies_processed": replies_processed,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    result = run_full_cycle()
    print(json.dumps(result, indent=2))
