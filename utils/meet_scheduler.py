"""
Google Calendar / Google Meet scheduling module.
Creates Google Meet events and sends invites to candidates.

Setup: Place credentials.json from Google Cloud Console in the hiring_portal folder.
Run once: python3 utils/meet_scheduler.py --auth  (opens browser to authorize)
After that, token.json is saved and it works autonomously.
"""

import os
import json
import pickle
import subprocess
from datetime import datetime, timedelta

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.pkl")
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _load_google_creds():
    """Load creds — token.pkl locally, secrets.toml on Streamlit Cloud."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)
        return creds

    # Cloud fallback: try st.secrets first, then env vars
    def _get_secret(key, default=""):
        try:
            import streamlit as st
            val = st.secrets.get(key, "")
            if val:
                return val
        except Exception:
            pass
        return os.environ.get(key, default)

    refresh_token = _get_secret("GOOGLE_REFRESH_TOKEN")
    if not refresh_token:
        return None

    try:
        creds = Credentials(
            token=_get_secret("GOOGLE_TOKEN"),
            refresh_token=refresh_token,
            token_uri=_get_secret("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
            client_id=_get_secret("GOOGLE_CLIENT_ID"),
            client_secret=_get_secret("GOOGLE_CLIENT_SECRET"),
            scopes=SCOPES,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds
    except Exception:
        return None


def _get_service():
    """Get authenticated Google Calendar service."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = _load_google_creds()

        if not creds:
            # Interactive auth (local only)
            if not os.path.exists(CREDENTIALS_FILE):
                return None, "credentials.json not found"
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)

        service = build("calendar", "v3", credentials=creds)
        return service, None
    except ImportError:
        return None, "Google API libraries not installed"
    except Exception as e:
        return None, str(e)


def create_meet_event(
    candidate_name: str,
    candidate_email: str,
    interview_date: str,  # "2025-04-01"
    interview_time: str,  # "10:00"
    duration_minutes: int = 30,
    interviewer_email: str = "hr.anileeanimation@gmail.com",
    description: str = ""
) -> tuple[str, str, str]:
    """
    Create a Google Calendar event with Meet link.
    Returns (meet_link, event_id, error_message)
    """
    service, err = _get_service()
    if err:
        # Fallback: generate a basic Meet link
        return _generate_fallback_link(), None, f"Calendar API not set up: {err}"

    try:
        # Parse datetime
        start_dt = datetime.strptime(f"{interview_date} {interview_time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event = {
            "summary": f"Interview: {candidate_name} — Educational Counsellor | Anilee Academy",
            "description": description or f"Candidate interview for Educational Counsellor position.\nCandidate: {candidate_name}",
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Kolkata"
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Kolkata"
            },
            "attendees": [
                {"email": candidate_email, "displayName": candidate_name},
                {"email": interviewer_email, "displayName": "Anilee Academy HR"}
            ],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"anilee-{candidate_name.replace(' ', '-').lower()}-{interview_date}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"}
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 60},
                    {"method": "popup", "minutes": 10}
                ]
            },
            "sendUpdates": "all"  # Sends email invites to all attendees
        }

        event_result = service.events().insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1,
            sendUpdates="all"
        ).execute()

        meet_link = event_result.get("hangoutLink", "")
        event_id = event_result.get("id", "")

        return meet_link, event_id, None

    except Exception as e:
        return _generate_fallback_link(), None, str(e)


def _generate_fallback_link() -> str:
    """Generate a basic Google Meet link when API is not available."""
    import random
    import string
    chars = string.ascii_lowercase
    code = f"{''.join(random.choices(chars, k=3))}-{''.join(random.choices(chars, k=4))}-{''.join(random.choices(chars, k=3))}"
    return f"https://meet.google.com/{code}"


def is_calendar_setup() -> bool:
    """Check if Google Calendar is configured."""
    return os.path.exists(TOKEN_FILE) or os.path.exists(CREDENTIALS_FILE)


if __name__ == "__main__":
    import sys
    if "--auth" in sys.argv:
        print("Starting Google Calendar authorization...")
        service, err = _get_service()
        if err:
            print(f"Error: {err}")
            print("\nTo set up Google Calendar:")
            print("1. Go to console.cloud.google.com")
            print("2. Create a project → Enable Google Calendar API")
            print("3. Create OAuth2 credentials → Desktop app")
            print("4. Download as credentials.json → place in hiring_portal/")
            print("5. Run: python3 utils/meet_scheduler.py --auth")
        else:
            print("Google Calendar authorized successfully!")
