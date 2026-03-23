"""
Indeed Employer Portal — Candidate Sourcer
==========================================
Imports candidates from the Indeed Candidates page (job applicants — FREE, full contact
details visible).  De-duplicates against the existing DB, adds new candidates, and
auto-sends the screening email to each one.

Usage
-----
  # One-off import (run from project root):
  python3 automation/indeed_sourcer.py

  # From Streamlit portal → Automation page → Indeed Sourcer tab:
  from automation.indeed_sourcer import run_import
  result = run_import()

How new candidates get in
-------------------------
When someone applies to your Indeed job posting their full CV (name, email, phone) is
visible for FREE in employers.indeed.com/candidates.  This module stores candidates
scraped from that page and re-imports daily (skipping duplicates by phone/email).
"""

import sys
import os
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import add_candidate, get_all_candidates, get_screening_questions, log_activity
from utils.email_service import send_screening_email

# ── Scraped candidates  ───────────────────────────────────────────────────────
# Last scraped: 2026-03-24 from https://employers.indeed.com/candidates
# Fields: name, phone, email, location, source, experience_months, notes, job_role
INDEED_CANDIDATES = [
    # ── Sales Executive applicants ─────────────────────────────────────────────
    {
        "name": "Akshay Ghorpade",
        "phone": "9021162765",
        "email": "akghorpade10@gmail.com",
        "location": "Satara",
        "source": "Indeed",
        "experience_months": 36,
        "notes": "Indeed applicant | Role: Sales Executive | MBA Finance, BDE at Inventive Infotech, HLF Marketing, Satara Pharma. Satara based.",
        "job_role": "Sales Executive",
    },
    {
        "name": "Sakshi Kamble",
        "phone": "8010851367",
        "email": "sakshikamble743@gmail.com",
        "location": "Satara",
        "source": "Indeed",
        "experience_months": 0,
        "notes": "Indeed applicant | Role: Sales Executive | Fresh grad B.A. Economics Shivaji University. From Shivthar, Satara 415011.",
        "job_role": "Sales Executive",
    },
    {
        "name": "Rushabh Kadam",
        "phone": "9860439186",
        "email": "Kadamrushabh64@gmail.com",
        "location": "Satara",
        "source": "Indeed",
        "experience_months": 0,
        "notes": "Indeed applicant | Role: Sales Executive | B.Tech Mechanical, Dnyanshree Institute Satara. Internship Niska Engineering & Tata Motors Satara.",
        "job_role": "Sales Executive",
    },
    {
        "name": "Prathamesh Jadhav",
        "phone": "9800657070",
        "email": "prathameshmaheshjadhavvqtin_2qv@indeedemail.com",
        "location": "Satara",
        "source": "Indeed",
        "experience_months": 30,
        "notes": "Indeed applicant | Role: Sales Executive | Gym Manager PMJ Fitness Satara (Oct 2022-present). B.Tech CS KBPCE Satara.",
        "job_role": "Sales Executive",
    },
    {
        "name": "Reshma Kadam",
        "phone": "9960845822",
        "email": "patoler249@gmail.com",
        "location": "Satara",
        "source": "Indeed",
        "experience_months": 18,
        "notes": "Indeed applicant | Role: Sales Executive | 1yr Sales + 6mo Recovery at Bajaj Finance. From Khatav, Dist Satara 415505.",
        "job_role": "Sales Executive",
    },
    {
        "name": "Apurva Pawar",
        "phone": "7499790036",
        "email": "apurvapawar910@gmail.com",
        "location": "Satara",
        "source": "Indeed",
        "experience_months": 0,
        "notes": "Indeed applicant | Role: Sales Executive | M.Sc. Physical Chemistry. Internship at Yashraj Ethanol Satara. From Arphal, Tal-Satara.",
        "job_role": "Sales Executive",
    },
    {
        "name": "Vikram Kalange",
        "phone": "9860438140",
        "email": "vikramkalangezi3rj_2o8@indeedemail.com",
        "location": "Satara",
        "source": "Indeed",
        "experience_months": 0,
        "notes": "Indeed applicant | Role: Sales Executive | BSc student. MS-CIT, Driving Licence. Satara 415004. Willing to relocate.",
        "job_role": "Sales Executive",
    },
    # ── Graphic Design Faculty applicants ─────────────────────────────────────
    {
        "name": "Shree Ghorpade",
        "phone": "7887754586",
        "email": "Shrikrushnghorpade40179@gmail.com",
        "location": "Satara",
        "source": "Indeed",
        "experience_months": 0,
        "notes": "Indeed applicant | Role: Graphic Design Faculty | B.A. grad, MS-CIT, Photoshop & CorelDraw. From Gojegaon, Tal/Dist Satara 415004.",
        "job_role": "Graphic Design Faculty",
    },
    {
        "name": "Gayatri Patil",
        "phone": "7385243415",
        "email": "patilgayatri634@gmail.com",
        "location": "Pune",
        "source": "Indeed",
        "experience_months": 12,
        "notes": "Indeed applicant | Role: Graphic Design Faculty | B.Animation Science YCIS Satara. Freelance + Codestrup Infotech Pune. 100+ daily posts.",
        "job_role": "Graphic Design Faculty",
    },
    {
        "name": "Amit Hadpidkar",
        "phone": "7397934324",
        "email": "amithadpidkar@gmail.com",
        "location": "Sindhudurg",
        "source": "Indeed",
        "experience_months": 20,
        "notes": "Indeed applicant | Role: Graphic Design Faculty | VFX Paint Prep at Cinegence & R.eflection, Faculty Arena Animation Kudal. BSc-IT + MAAC Pune.",
        "job_role": "Graphic Design Faculty",
    },
    {
        "name": "Piyush Gupta",
        "phone": "7428522416",
        "email": "guptapiyush@axiscolleges.in",
        "location": "Kanpur",
        "source": "Indeed",
        "experience_months": 144,
        "notes": "Indeed applicant | Role: Graphic Design Faculty | Asst Prof Axis Colleges Kanpur. MFA Amity University. 12+ yrs. Location: Kanpur UP.",
        "job_role": "Graphic Design Faculty",
    },
    {
        "name": "Somenath Mistry",
        "phone": "9305976478",
        "email": "Somenathmistry1985@gmail.com",
        "location": "Kolkata",
        "source": "Indeed",
        "experience_months": 144,
        "notes": "Indeed applicant | Role: Graphic Design Faculty | 12+ yrs Graphic Design & 2D Animation. Dream Zone faculty Kolkata. Location: Kolkata WB.",
        "job_role": "Graphic Design Faculty",
    },
]


# ── Dedup helpers ─────────────────────────────────────────────────────────────

def _normalize_phone(phone: str) -> str:
    """Strip country code, spaces, dashes — keep 10 digits."""
    digits = "".join(c for c in str(phone) if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def _existing_phones_emails() -> tuple[set, set]:
    """Return sets of normalized phones and lowered emails already in DB."""
    all_cands = get_all_candidates()
    phones = {_normalize_phone(c.get("phone", "")) for c in all_cands if c.get("phone")}
    emails = {(c.get("email") or "").lower().strip() for c in all_cands if c.get("email")}
    return phones, emails


def is_duplicate(candidate: dict, existing_phones: set, existing_emails: set) -> bool:
    phone = _normalize_phone(candidate.get("phone", ""))
    email = (candidate.get("email") or "").lower().strip()
    if phone and phone in existing_phones:
        return True
    if email and email in existing_emails:
        return True
    return False


# ── Email sender ──────────────────────────────────────────────────────────────

def _send_email_async(candidate_id: int, name: str, email: str, questions: list):
    """Fire-and-forget screening email in a background thread."""
    def _worker():
        try:
            ok, msg = send_screening_email(name, email, questions, candidate_id)
            if ok:
                log_activity(candidate_id, name, "Screening Email Sent",
                             f"Auto-sent via Indeed Sourcer to {email}", "Indeed Sourcer")
        except Exception:
            pass
    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ── Main import function ──────────────────────────────────────────────────────

def run_import(
    candidates: list = None,
    send_emails: bool = True,
    local_only: bool = False
) -> dict:
    """
    Import Indeed candidates into the portal DB.

    Parameters
    ----------
    candidates   : list of candidate dicts (defaults to INDEED_CANDIDATES)
    send_emails  : whether to auto-send screening email to each new candidate
    local_only   : if True, skip email sending (dry-run / testing)

    Returns
    -------
    dict with keys: added, skipped_duplicates, email_queued, errors, details
    """
    if candidates is None:
        candidates = INDEED_CANDIDATES

    result = {
        "added": 0,
        "skipped_duplicates": 0,
        "email_queued": 0,
        "errors": [],
        "details": [],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    existing_phones, existing_emails = _existing_phones_emails()
    questions = get_screening_questions(enabled_only=True) if send_emails else []

    for cand in candidates:
        name  = cand.get("name", "").strip()
        phone = cand.get("phone", "").strip()
        email = cand.get("email", "").strip()

        if not name:
            result["errors"].append("Skipped: candidate with no name")
            continue

        if is_duplicate(cand, existing_phones, existing_emails):
            result["skipped_duplicates"] += 1
            result["details"].append({"name": name, "status": "duplicate", "phone": phone})
            # Update sets so subsequent duplicates are also caught
            if phone:
                existing_phones.add(_normalize_phone(phone))
            if email:
                existing_emails.add(email.lower())
            continue

        try:
            cid = add_candidate(
                name=name,
                phone=phone,
                email=email,
                source=cand.get("source", "Indeed"),
                location=cand.get("location", "Satara"),
                experience_months=cand.get("experience_months", 0),
                expected_salary=cand.get("expected_salary", 0),
                notes=cand.get("notes", ""),
            )
            result["added"] += 1
            detail = {"name": name, "status": "added", "id": cid, "phone": phone, "email": email}

            # Track to avoid adding same phone/email twice within this batch
            if phone:
                existing_phones.add(_normalize_phone(phone))
            if email:
                existing_emails.add(email.lower())

            # Send screening email
            if send_emails and not local_only and email:
                _send_email_async(cid, name, email, questions)
                result["email_queued"] += 1
                detail["email_sent"] = True
            else:
                detail["email_sent"] = False

            result["details"].append(detail)

        except Exception as e:
            result["errors"].append(f"{name}: {e}")

    return result


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("  Anilee Hiring Portal — Indeed Candidate Importer")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Ask before sending emails when running from CLI
    answer = input("\nSend screening emails to new candidates? [y/N]: ").strip().lower()
    send = answer == "y"

    print(f"\nImporting {len(INDEED_CANDIDATES)} candidates (send_emails={send}) …\n")
    res = run_import(send_emails=send)

    print(f"✅  Added         : {res['added']}")
    print(f"⏭   Duplicates    : {res['skipped_duplicates']}")
    print(f"📧  Emails queued : {res['email_queued']}")
    if res["errors"]:
        print(f"❌  Errors        : {len(res['errors'])}")
        for e in res["errors"]:
            print(f"     {e}")

    print("\nDetails:")
    for d in res["details"]:
        icon = "✅" if d["status"] == "added" else "⏭"
        print(f"  {icon} {d['name']:<25} {d['status']:<12} {d.get('email','')}")

    print("\nDone.\n")
