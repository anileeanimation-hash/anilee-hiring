"""
Gmail automation module — sends emails via Gmail API, reads replies via Gmail API.
Uses hr.anileeanimation@gmail.com via OAuth2 (shared token.pkl with meet_scheduler).
No App Password needed.
"""

import os
import base64
import pickle
import re
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# Base URL for the screening form
def _get_portal_url() -> str:
    url = os.environ.get("PORTAL_BASE_URL", "")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("PORTAL_BASE_URL", "")
        except Exception:
            pass
    return url.rstrip("/") if url else "http://localhost:8503"


def _form_token(candidate_id: int) -> str:
    """Generate a secure token for the screening form link."""
    secret = "anilee2026"
    return hashlib.md5(f"{candidate_id}-{secret}".encode()).hexdigest()[:12]


def get_screening_form_url(candidate_id: int) -> str:
    """Build the screening form URL for a candidate."""
    token = _form_token(candidate_id)
    base = _get_portal_url()
    return f"{base}/Screening_Form?cid={candidate_id}&token={token}"

TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.pkl")
GMAIL_USER = "hr.anileeanimation@gmail.com"


def _load_google_creds():
    """Load Google OAuth2 credentials — token.pkl first, secrets.toml fallback (for cloud)."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    # ── Local: use token.pkl ──────────────────────────────────────────────────
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)
        return creds

    # ── Cloud: build from secrets.toml ────────────────────────────────────────
    try:
        import streamlit as st
        s = st.secrets
        creds = Credentials(
            token=s.get("GOOGLE_TOKEN", ""),
            refresh_token=s.get("GOOGLE_REFRESH_TOKEN", ""),
            token_uri=s.get("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
            client_id=s.get("GOOGLE_CLIENT_ID", ""),
            client_secret=s.get("GOOGLE_CLIENT_SECRET", ""),
            scopes=[
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.modify",
            ]
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds
    except Exception:
        return None


def _get_gmail_service():
    """Get authenticated Gmail API service."""
    try:
        from googleapiclient.discovery import build
        creds = _load_google_creds()
        if not creds:
            return None, "Google credentials not found. Run auth or set secrets."
        service = build("gmail", "v1", credentials=creds)
        return service, None
    except ImportError:
        return None, "Google API libraries not installed."
    except Exception as e:
        return None, str(e)


def _build_message(to_email: str, to_name: str, subject: str,
                   body_html: str, body_text: str = "") -> dict:
    """Build a Gmail API message object."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Anilee Academy HR <{GMAIL_USER}>"
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
    msg["Reply-To"] = GMAIL_USER

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def send_email(to_email: str, to_name: str, subject: str,
               body_html: str, body_text: str = "") -> tuple[bool, str]:
    """Send email via Gmail API. Returns (success, message)."""
    service, err = _get_gmail_service()
    if err:
        return False, f"Gmail not configured: {err}"

    try:
        message = _build_message(to_email, to_name, subject, body_html, body_text)
        service.users().messages().send(userId="me", body=message).execute()
        return True, "Email sent successfully"
    except Exception as e:
        return False, f"Email failed: {str(e)}"


def is_gmail_setup() -> bool:
    """Check if Gmail API is configured."""
    return os.path.exists(TOKEN_FILE)


def send_screening_email(candidate_name: str, candidate_email: str,
                          enabled_questions: list, candidate_id: int) -> tuple[bool, str]:
    """Send screening email with a form link — no email Q&A."""
    form_url = get_screening_form_url(candidate_id)
    deadline = (datetime.now() + timedelta(days=2)).strftime('%d %b %Y')
    subject = "Anilee Academy — Next Step: Quick Screening Form (3 mins)"

    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#FF6B35;padding:20px 28px;border-radius:10px 10px 0 0;">
        <h2 style="color:white;margin:0;">🎓 Anilee Academy, Satara</h2>
        <p style="color:rgba(255,255,255,0.9);margin:6px 0 0;">Educational Counsellor — Screening Step</p>
      </div>
      <div style="padding:28px;background:#fff;border:1px solid #e0e0e0;">
        <p style="font-size:16px;">Namaste <b>{candidate_name}</b>,</p>
        <p>Thank you for applying! We have reviewed your profile and would like to move you to
        the next step.</p>
        <p>Please fill a <b>short screening form</b> (takes only 3–5 minutes) by clicking the
        button below:</p>

        <div style="text-align:center;margin:28px 0;">
          <a href="{form_url}"
             style="background:#FF6B35;color:white;padding:14px 36px;border-radius:8px;
                    text-decoration:none;font-size:17px;font-weight:bold;display:inline-block;">
            📝 Fill Screening Form
          </a>
        </div>

        <p style="background:#fff8e1;padding:12px 16px;border-radius:6px;
                  border-left:4px solid #FFC107;font-size:14px;">
          📅 <b>Deadline:</b> {deadline}<br>
          💰 <b>Salary Range:</b> ₹15,000 – ₹25,000/month based on experience<br>
          📍 <b>Location:</b> Satara, Maharashtra (In-office)
        </p>

        <p style="font-size:14px;">After submitting, our HR team will review your answers and
        contact you within <b>2–3 working days</b>. Shortlisted candidates will be called for
        a personal interview.</p>

        <p style="font-size:13px;color:#888;margin-top:20px;">
          If the button doesn't work, copy and paste this link in your browser:<br>
          <a href="{form_url}" style="color:#1976D2;word-break:break-all;">{form_url}</a>
        </p>
      </div>
      <div style="background:#f5f5f5;padding:12px;text-align:center;font-size:12px;
                  color:#888;border-radius:0 0 10px 10px;">
        Anilee Academy | Satara, Maharashtra | hr.anileeanimation@gmail.com
      </div>
    </div>
    """

    body_text = f"""Namaste {candidate_name},

Thank you for applying for the Educational Counsellor position at Anilee Academy, Satara.

Please fill our short screening form (3-5 minutes) using the link below:
{form_url}

Deadline: {deadline}
Salary: ₹15,000 – ₹25,000/month | Location: Satara (In-office)

After submitting, our HR team will review your answers and contact you within 2-3 working days.

Regards,
HR Team — Anilee Academy"""

    return send_email(candidate_email, candidate_name, subject, body_html, body_text)


def send_interview_invite(candidate_name: str, candidate_email: str,
                           interview_date: str, interview_time: str,
                           meet_link: str, interviewer: str = "HR") -> tuple[bool, str]:
    """Send Google Meet interview invite to candidate."""
    subject = f"Interview Scheduled — Anilee Academy Educational Counsellor | {interview_date}"

    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#198754;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">🎉 Interview Confirmed — Anilee Academy</h2>
      </div>
      <div style="padding:24px;background:#fff;border:1px solid #e0e0e0;">
        <p>Namaste <b>{candidate_name}</b>,</p>
        <p>Congratulations! You have been shortlisted for an interview for the
        <b>Educational Counsellor</b> position at Anilee Academy.</p>

        <div style="background:#e8f5e9;padding:16px;border-radius:8px;margin:16px 0;">
          <h3 style="margin:0 0 12px;color:#198754;">Interview Details</h3>
          <p style="margin:4px 0;">📅 <b>Date:</b> {interview_date}</p>
          <p style="margin:4px 0;">⏰ <b>Time:</b> {interview_time}</p>
          <p style="margin:4px 0;">👤 <b>Interviewer:</b> {interviewer}</p>
          <p style="margin:8px 0 0;">
            🔗 <b>Google Meet Link:</b>
            <a href="{meet_link}" style="color:#1976D2;">{meet_link}</a>
          </p>
        </div>

        <p><b>Please keep ready:</b></p>
        <ul>
          <li>A quiet place with good internet connection</li>
          <li>Your resume / any experience certificates</li>
          <li>Be on time — interview will start as scheduled</li>
        </ul>
        <p>For any queries, contact: hr.anileeanimation@gmail.com</p>
      </div>
      <div style="background:#f5f5f5;padding:12px;text-align:center;font-size:12px;color:#888;">
        Anilee Academy | Satara, Maharashtra
      </div>
    </div>
    """

    body_text = f"""Namaste {candidate_name},

Your interview has been scheduled for the Educational Counsellor position.

Date: {interview_date}
Time: {interview_time}
Interviewer: {interviewer}
Google Meet Link: {meet_link}

Please join 2 minutes early.
Contact: hr.anileeanimation@gmail.com

Regards, HR Team — Anilee Academy"""

    return send_email(candidate_email, candidate_name, subject, body_html, body_text)


def send_rejection_email(candidate_name: str, candidate_email: str) -> tuple[bool, str]:
    """Send polite rejection email."""
    subject = "Anilee Academy — Application Update"
    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;">
      <h2>Anilee Academy, Satara</h2>
      <p>Namaste <b>{candidate_name}</b>,</p>
      <p>Thank you for your interest in the Educational Counsellor position at Anilee Academy.</p>
      <p>After careful consideration, we have decided to move forward with other candidates whose
      profile more closely matches our current requirements.</p>
      <p>We wish you the very best in your job search and encourage you to apply for future
      openings with us.</p>
      <p>Regards,<br><b>HR Team — Anilee Academy</b><br>Satara, Maharashtra</p>
    </div>"""
    return send_email(candidate_email, candidate_name, subject, body_html)


def send_hr_notification(subject: str, body: str) -> tuple[bool, str]:
    """Send notification to HR email."""
    return send_email(GMAIL_USER, "Anilee Academy HR", subject,
                      f"<pre style='font-family:Arial'>{body}</pre>", body)


def read_candidate_replies(since_hours: int = 48) -> list[dict]:
    """
    Read unread email replies from candidates via Gmail API.
    Returns list of {from_email, from_name, subject, body, candidate_id, received_at, message_id}
    """
    service, err = _get_gmail_service()
    if err:
        print(f"Gmail API error: {err}")
        return []

    replies = []
    try:
        since_ts = int((datetime.now() - timedelta(hours=since_hours)).timestamp())
        query = f"is:unread in:inbox after:{since_ts}"

        result = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
        messages = result.get("messages", [])

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()

            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            from_header = headers.get("From", "")
            subject = headers.get("Subject", "")
            date = headers.get("Date", "")

            # Parse sender
            from_match = re.match(r'"?([^"<]+)"?\s*<?([^>]+)>?', from_header)
            from_name = from_match.group(1).strip() if from_match else ""
            from_email = from_match.group(2).strip() if from_match else from_header

            # Skip emails from ourselves
            if GMAIL_USER in from_email:
                continue

            # Extract body
            body = _extract_body(msg["payload"])

            # Extract candidate ID from subject/body
            cand_id_match = re.search(r'CAND-(\d+)', subject + body)
            candidate_id = int(cand_id_match.group(1)) if cand_id_match else None

            replies.append({
                "from_email": from_email,
                "from_name": from_name,
                "subject": subject,
                "body": body[:3000],
                "candidate_id": candidate_id,
                "received_at": date,
                "message_id": msg_ref["id"]
            })

    except Exception as e:
        print(f"Gmail read error: {e}")

    return replies


def _extract_body(payload: dict) -> str:
    """Recursively extract plain text body from Gmail message payload."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    if "parts" in payload:
        for part in payload["parts"]:
            text = _extract_body(part)
            if text:
                return text

    return ""


def mark_as_read(message_id: str) -> bool:
    """Mark a Gmail message as read."""
    service, err = _get_gmail_service()
    if err:
        return False
    try:
        service.users().messages().modify(
            userId="me", id=message_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        return True
    except Exception:
        return False
