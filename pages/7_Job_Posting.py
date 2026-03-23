"""
Job Posting — HR enters job requirement, system posts to Work India + Indeed automatically.
"""
import streamlit as st
import sys
import os
import subprocess
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import log_activity

st.set_page_config(page_title="Job Posting — Anilee Hiring", page_icon="📢", layout="wide")
st.title("📢 Job Posting Automation")
st.caption("Post jobs to Work India and Indeed with one click")

# Pre-filled templates per role
JOB_TEMPLATES = {
    "Educational Counsellor": {
        "title": "Educational Counsellor — Anilee Academy, Satara",
        "experience": "0-2 years",
        "salary_min": 15000,
        "salary_max": 25000,
        "skills": "Sales, Counselling, Lead Conversion, Target Achievement",
        "description": """We are hiring an Educational Counsellor at Anilee Academy — a leading Animation & Skill Training Institute in Satara.

Role: Convert student enquiries into admissions. Handle walk-ins, calls, and online leads. Achieve monthly admission targets.

Requirements:
- Min 3 months experience in sales, admissions or counselling
- Fluent Marathi speaker (essential)
- Target-driven and persuasive personality
- Based in Satara or nearby

Salary: ₹15,000 – ₹25,000/month based on experience
Location: Satara, Maharashtra (In-office)
""",
        "vacancies": 1
    },
    "Telecalling Executive": {
        "title": "Telecalling Executive — Anilee Academy, Satara",
        "experience": "0-1 years",
        "salary_min": 10000,
        "salary_max": 15000,
        "skills": "Telecalling, Communication, Lead Generation",
        "description": "Telecalling executive for animation institute. Handle inbound and outbound calls to prospective students.",
        "vacancies": 2
    },
    "Sales Executive (Field)": {
        "title": "Field Sales Executive — Anilee Academy, Satara",
        "experience": "0-2 years",
        "salary_min": 12000,
        "salary_max": 20000,
        "skills": "Field Sales, B2C Sales, Lead Generation, Communication",
        "description": "On-field business development and student acquisition for our animation institute.",
        "vacancies": 1
    },
    "Faculty — Animation": {
        "title": "Animation Faculty — Anilee Academy, Satara",
        "experience": "1-3 years",
        "salary_min": 18000,
        "salary_max": 30000,
        "skills": "Maya, After Effects, Photoshop, 2D/3D Animation",
        "description": "Teach animation courses (2D, 3D, VFX) to students. Portfolio required.",
        "vacancies": 1
    },
    "Custom Role": {
        "title": "",
        "experience": "0-2 years",
        "salary_min": 10000,
        "salary_max": 25000,
        "skills": "",
        "description": "",
        "vacancies": 1
    }
}

# Role selector
role = st.selectbox("Select Role to Post", list(JOB_TEMPLATES.keys()))
template = JOB_TEMPLATES[role]

st.divider()

# Job Details Form
with st.form("job_post_form"):
    st.subheader("Job Details")
    c1, c2 = st.columns(2)

    with c1:
        job_title = st.text_input("Job Title", value=template["title"])
        experience = st.text_input("Experience Required", value=template["experience"])
        skills = st.text_input("Key Skills", value=template["skills"])
        vacancies = st.number_input("Number of Vacancies", 1, 10, value=template["vacancies"])

    with c2:
        salary_min = st.number_input("Min Salary (₹)", 5000, 100000, value=template["salary_min"], step=500)
        salary_max = st.number_input("Max Salary (₹)", 5000, 100000, value=template["salary_max"], step=500)
        location = st.text_input("Location", value="Satara, Maharashtra")
        industry = st.text_input("Industry", value="Education / Animation / Training")

    description = st.text_area("Job Description", value=template["description"], height=200)

    st.markdown("**Post to Platforms:**")
    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        post_workindia = st.checkbox("Work India", value=True)
    with pc2:
        post_indeed = st.checkbox("Indeed India", value=True)
    with pc3:
        post_apna = st.checkbox("Apna", value=False)

    submitted = st.form_submit_button("📢 Post Job Now", type="primary", use_container_width=True)

if submitted:
    job_data = {
        "title": job_title, "experience": experience, "skills": skills,
        "vacancies": vacancies, "salary_min": salary_min, "salary_max": salary_max,
        "location": location, "description": description,
        "platforms": {
            "work_india": post_workindia,
            "indeed": post_indeed,
            "apna": post_apna
        }
    }

    # Save job data for the posting script
    job_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "automation", "pending_job.json")
    with open(job_file, "w") as f:
        json.dump(job_data, f, indent=2)

    results = {}

    if post_workindia:
        with st.spinner("Posting to Work India..."):
            try:
                r = subprocess.run(
                    ["python3", "automation/post_job.py", "--platform", "workindia",
                     "--job-file", job_file],
                    capture_output=True, text=True, timeout=120,
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                results["Work India"] = "✅ Posted!" if r.returncode == 0 else f"⚠️ {r.stderr[:100]}"
            except Exception as e:
                results["Work India"] = f"⚠️ Script error: {e}"

    if post_indeed:
        with st.spinner("Posting to Indeed..."):
            try:
                r = subprocess.run(
                    ["python3", "automation/post_job.py", "--platform", "indeed",
                     "--job-file", job_file],
                    capture_output=True, text=True, timeout=120,
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                results["Indeed"] = "✅ Posted!" if r.returncode == 0 else f"⚠️ {r.stderr[:100]}"
            except Exception as e:
                results["Indeed"] = f"⚠️ Script error: {e}"

    # Show results
    st.subheader("Posting Results")
    for platform, status in results.items():
        if "✅" in status:
            st.success(f"{platform}: {status}")
        else:
            st.warning(f"{platform}: {status}")
            st.info("👉 See instructions below for manual posting steps.")

    log_activity(0, "System", "Job Posted",
                 f"{job_title} — {', '.join(p for p, v in job_data['platforms'].items() if v)}", "HR")

st.divider()

# Manual posting instructions
with st.expander("📋 Manual Posting Instructions (if auto-post fails)"):
    st.markdown("""
    ### Work India (workindia.in)
    1. Go to `workindia.in/employer` — already signed in on Chrome
    2. Click **Post a Job**
    3. Fill: Title, Salary, Location (Satara), Experience, Skills
    4. Paste the job description above
    5. Set: **Immediate Joining** | **Full Time**
    6. Submit → candidates start applying within hours

    ### Indeed India (indeed.com)
    1. Go to `employer.indeed.com` — already signed in on Chrome
    2. Click **Post a Job**
    3. Fill all details | Location: **Satara, Maharashtra**
    4. Set salary range: ₹{salary_min:,} – ₹{salary_max:,}/month
    5. Screening questions: Add "Are you based in Satara?" as screener
    6. Submit

    ### Apna (apna.co)
    1. Go to `apna.co/employer` — create account if needed
    2. Post under **Sales & Business Development** category
    3. Enable **Chat with candidates** for faster response
    """.format(salary_min=template["salary_min"], salary_max=template["salary_max"]))

# Active job posts tracker
st.subheader("Active Job Posts")
job_log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "automation", "job_history.json")
if os.path.exists(job_log_file):
    with open(job_log_file) as f:
        history = json.load(f)
    for h in history[-5:]:
        st.markdown(f"- **{h.get('title', '?')}** — Posted on {h.get('date', '?')} | {h.get('platforms', '')}")
else:
    st.info("No job posts yet. Post your first job above.")
