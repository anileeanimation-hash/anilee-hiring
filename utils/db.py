import sqlite3
import os
from datetime import datetime

_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hiring.db")
# On Streamlit Cloud /mount/src is read-only — fall back to /tmp
if not os.access(os.path.dirname(_DEFAULT_DB), os.W_OK):
    DB_PATH = "/tmp/hiring.db"
else:
    DB_PATH = _DEFAULT_DB

STAGES = ["New", "Outreached", "Screening", "Screened", "Interview Scheduled", "Hired", "Rejected"]
SOURCES = ["Work India", "Apna", "Indeed", "Manual", "Referral", "Walk-In", "WhatsApp"]


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row):
    return dict(row) if row else None


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL DEFAULT '',
        phone TEXT DEFAULT '',
        email TEXT DEFAULT '',
        source TEXT DEFAULT 'Manual',
        stage TEXT DEFAULT 'New',
        score INTEGER DEFAULT 0,
        score_band TEXT DEFAULT 'Unscored',
        ai_summary TEXT DEFAULT '',
        location TEXT DEFAULT 'Satara',
        experience_months INTEGER DEFAULT 0,
        current_salary INTEGER DEFAULT 0,
        expected_salary INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    );

    CREATE TABLE IF NOT EXISTS screening_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        category TEXT DEFAULT 'General',
        is_hard_filter INTEGER DEFAULT 0,
        is_enabled INTEGER DEFAULT 1,
        weight INTEGER DEFAULT 1,
        order_index INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now', 'localtime'))
    );

    CREATE TABLE IF NOT EXISTS candidate_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL,
        question_id INTEGER,
        question_text TEXT DEFAULT '',
        response TEXT DEFAULT '',
        ai_score INTEGER DEFAULT 0,
        ai_feedback TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    );

    CREATE TABLE IF NOT EXISTS interviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL,
        candidate_name TEXT DEFAULT '',
        candidate_phone TEXT DEFAULT '',
        scheduled_date TEXT DEFAULT '',
        scheduled_time TEXT DEFAULT '',
        duration_minutes INTEGER DEFAULT 30,
        interviewer TEXT DEFAULT 'HR',
        mode TEXT DEFAULT 'In Person',
        status TEXT DEFAULT 'Scheduled',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    );

    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        candidate_name TEXT DEFAULT '',
        action TEXT DEFAULT '',
        details TEXT DEFAULT '',
        performed_by TEXT DEFAULT 'System',
        created_at TEXT DEFAULT (datetime('now', 'localtime'))
    );
    """)

    # Seed default screening questions
    c.execute("SELECT COUNT(*) FROM screening_questions")
    if c.fetchone()[0] == 0:
        questions = [
            # Hard filters (is_hard_filter=1)
            ("Are you currently based in Satara or nearby (within 20 km)?", "Location", 1, 1, 3, 1),
            ("Can you speak and communicate fluently in Marathi?", "Language", 1, 1, 3, 2),
            ("Do you have at least 3 months of experience in sales, counselling, or admissions?", "Experience", 1, 1, 3, 3),
            # Soft scoring questions (is_hard_filter=0)
            ("How many years of experience do you have in sales, counselling, or admissions?", "Experience", 0, 1, 2, 4),
            ("Have you previously worked in an education institution, edtech company, or training academy?", "Background", 0, 1, 1, 5),
            ("Are you comfortable with a role that has monthly revenue and admission targets?", "Mindset", 0, 1, 2, 6),
            ("How many leads have you typically handled per day or week in your previous role?", "Capacity", 0, 1, 1, 7),
            ("What is your personal follow-up strategy for leads that go silent after the first interaction?", "Skills", 0, 1, 2, 8),
            ("Describe a time you converted a cold or hesitant lead into a paid customer. What exactly did you do?", "Skills", 0, 1, 3, 9),
            ("What motivates you more — a fixed salary or a structure where your income grows with your performance?", "Mindset", 0, 1, 2, 10),
            ("Why do you want to work specifically in the education sector?", "Motivation", 0, 1, 1, 11),
            ("How do you handle a prospect who says 'I will think about it and get back to you'?", "Skills", 0, 1, 2, 12),
            ("How do you personally handle rejection emotionally when a confident lead does not convert?", "Resilience", 0, 1, 2, 13),
            ("How quickly can you join if selected?", "Availability", 0, 1, 1, 14),
            ("What are your salary expectations?", "Compensation", 0, 1, 1, 15),
        ]
        c.executemany(
            "INSERT INTO screening_questions (question, category, is_hard_filter, is_enabled, weight, order_index) VALUES (?,?,?,?,?,?)",
            questions
        )

    conn.commit()
    conn.close()


# ── PIPELINE STATS ──────────────────────────────────────────────────────────

def get_pipeline_stats():
    conn = get_connection()
    c = conn.cursor()
    stats = {}
    c.execute("SELECT COUNT(*) FROM candidates WHERE stage != 'Rejected'")
    stats['total'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM candidates WHERE score_band = 'Hot 🔥'")
    stats['hot'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM candidates WHERE stage = 'Screening'")
    stats['screening'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM interviews WHERE status = 'Scheduled'")
    stats['interviews'] = c.fetchone()[0]
    c.execute("""SELECT COUNT(*) FROM candidates WHERE stage = 'Hired'
                 AND strftime('%Y-%m', updated_at) = strftime('%Y-%m', datetime('now', 'localtime'))""")
    stats['hired'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM candidates WHERE stage = 'Rejected'")
    stats['rejected'] = c.fetchone()[0]
    conn.close()
    return stats


def get_recent_activity(limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = rows_to_dicts(c.fetchall())
    conn.close()
    return rows


# ── CANDIDATES ───────────────────────────────────────────────────────────────

def add_candidate(name, phone, email='', source='Manual', location='Satara',
                  experience_months=0, expected_salary=0, notes=''):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO candidates (name, phone, email, source, location,
                 experience_months, expected_salary, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (name, phone, email, source, location, experience_months, expected_salary, notes))
    cid = c.lastrowid
    _log(c, cid, name, "Added to Pipeline", f"Source: {source}", "HR")
    conn.commit()
    conn.close()
    return cid


def get_all_candidates(stage_filter=None, source_filter=None, band_filter=None, search=None):
    conn = get_connection()
    c = conn.cursor()
    query = "SELECT * FROM candidates WHERE 1=1"
    params = []
    if stage_filter:
        query += " AND stage = ?"
        params.append(stage_filter)
    if source_filter:
        query += " AND source = ?"
        params.append(source_filter)
    if band_filter:
        query += " AND score_band = ?"
        params.append(band_filter)
    if search:
        query += " AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])
    query += " ORDER BY created_at DESC"
    c.execute(query, params)
    rows = rows_to_dicts(c.fetchall())
    conn.close()
    return rows


def get_candidates_by_stage():
    conn = get_connection()
    c = conn.cursor()
    result = {}
    for stage in STAGES:
        c.execute("SELECT * FROM candidates WHERE stage = ? ORDER BY score DESC", (stage,))
        result[stage] = rows_to_dicts(c.fetchall())
    conn.close()
    return result


def get_candidate(candidate_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
    row = dict_from_row(c.fetchone())
    conn.close()
    return row


def update_candidate(candidate_id, **kwargs):
    if not kwargs:
        return
    conn = get_connection()
    c = conn.cursor()
    kwargs['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    set_clause = ", ".join([f"{k} = ?" for k in kwargs])
    values = list(kwargs.values()) + [candidate_id]
    c.execute(f"UPDATE candidates SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def update_candidate_stage(candidate_id, new_stage, performed_by="HR"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name, stage FROM candidates WHERE id = ?", (candidate_id,))
    row = c.fetchone()
    if row:
        old_stage = row['stage']
        name = row['name']
        c.execute("UPDATE candidates SET stage = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                  (new_stage, candidate_id))
        _log(c, candidate_id, name, "Stage Changed", f"{old_stage} → {new_stage}", performed_by)
    conn.commit()
    conn.close()


def update_candidate_score(candidate_id, score, score_band, ai_summary=''):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""UPDATE candidates SET score = ?, score_band = ?, ai_summary = ?,
                 updated_at = datetime('now', 'localtime') WHERE id = ?""",
              (score, score_band, ai_summary, candidate_id))
    c.execute("SELECT name FROM candidates WHERE id = ?", (candidate_id,))
    row = c.fetchone()
    if row:
        _log(c, candidate_id, row['name'], "Score Updated",
             f"Score: {score}% — {score_band}", "AI System")
    conn.commit()
    conn.close()


def delete_candidate(candidate_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM candidates WHERE id = ?", (candidate_id,))
    row = c.fetchone()
    if row:
        c.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
        c.execute("DELETE FROM candidate_responses WHERE candidate_id = ?", (candidate_id,))
        c.execute("DELETE FROM interviews WHERE candidate_id = ?", (candidate_id,))
        _log(c, candidate_id, row['name'], "Deleted", "", "HR")
    conn.commit()
    conn.close()


def import_candidates_from_csv(rows):
    added, errors = 0, []
    for row in rows:
        try:
            add_candidate(
                name=str(row.get('name', '')).strip(),
                phone=str(row.get('phone', '')).strip(),
                email=str(row.get('email', '')).strip(),
                source=str(row.get('source', 'Import')).strip(),
                location=str(row.get('location', 'Satara')).strip(),
                experience_months=int(float(row.get('experience_months', 0) or 0)),
                expected_salary=int(float(row.get('expected_salary', 0) or 0)),
                notes=str(row.get('notes', '')).strip()
            )
            added += 1
        except Exception as e:
            errors.append(f"{row.get('name', 'Unknown')}: {e}")
    return added, errors


# ── SCREENING QUESTIONS ──────────────────────────────────────────────────────

def get_screening_questions(enabled_only=False):
    conn = get_connection()
    c = conn.cursor()
    if enabled_only:
        c.execute("SELECT * FROM screening_questions WHERE is_enabled = 1 ORDER BY order_index")
    else:
        c.execute("SELECT * FROM screening_questions ORDER BY order_index")
    rows = rows_to_dicts(c.fetchall())
    conn.close()
    return rows


def toggle_question(question_id, is_enabled):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE screening_questions SET is_enabled = ? WHERE id = ?",
              (1 if is_enabled else 0, question_id))
    conn.commit()
    conn.close()


def update_question_weight(question_id, weight):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE screening_questions SET weight = ? WHERE id = ?", (weight, question_id))
    conn.commit()
    conn.close()


# ── CANDIDATE RESPONSES ──────────────────────────────────────────────────────

def save_response(candidate_id, question_id, question_text, response_text, ai_score=0, ai_feedback=''):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM candidate_responses WHERE candidate_id = ? AND question_id = ?",
              (candidate_id, question_id))
    existing = c.fetchone()
    if existing:
        c.execute("""UPDATE candidate_responses SET response = ?, ai_score = ?, ai_feedback = ?
                     WHERE candidate_id = ? AND question_id = ?""",
                  (response_text, ai_score, ai_feedback, candidate_id, question_id))
    else:
        c.execute("""INSERT INTO candidate_responses
                     (candidate_id, question_id, question_text, response, ai_score, ai_feedback)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (candidate_id, question_id, question_text, response_text, ai_score, ai_feedback))
    conn.commit()
    conn.close()


def get_candidate_responses(candidate_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM candidate_responses WHERE candidate_id = ? ORDER BY question_id",
              (candidate_id,))
    rows = rows_to_dicts(c.fetchall())
    conn.close()
    return rows


# ── INTERVIEWS ───────────────────────────────────────────────────────────────

def add_interview(candidate_id, candidate_name, candidate_phone, scheduled_date,
                  scheduled_time, duration_minutes=30, interviewer="HR",
                  mode="In Person", notes=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO interviews
                 (candidate_id, candidate_name, candidate_phone, scheduled_date,
                  scheduled_time, duration_minutes, interviewer, mode, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (candidate_id, candidate_name, candidate_phone, scheduled_date,
               scheduled_time, duration_minutes, interviewer, mode, notes))
    c.execute("""UPDATE candidates SET stage = 'Interview Scheduled',
                 updated_at = datetime('now', 'localtime') WHERE id = ?""",
              (candidate_id,))
    _log(c, candidate_id, candidate_name, "Interview Scheduled",
         f"{scheduled_date} at {scheduled_time}", "HR")
    conn.commit()
    conn.close()


def get_all_interviews():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM interviews ORDER BY scheduled_date DESC, scheduled_time DESC")
    rows = rows_to_dicts(c.fetchall())
    conn.close()
    return rows


def update_interview_status(interview_id, status, notes=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT candidate_id, candidate_name FROM interviews WHERE id = ?", (interview_id,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE interviews SET status = ?, notes = ? WHERE id = ?",
                  (status, notes, interview_id))
        if status == "Completed - Hired":
            c.execute("""UPDATE candidates SET stage = 'Hired',
                         updated_at = datetime('now', 'localtime') WHERE id = ?""",
                      (row['candidate_id'],))
        elif status == "Completed - Rejected":
            c.execute("""UPDATE candidates SET stage = 'Rejected',
                         updated_at = datetime('now', 'localtime') WHERE id = ?""",
                      (row['candidate_id'],))
        _log(c, row['candidate_id'], row['candidate_name'], "Interview Updated", status, "HR")
    conn.commit()
    conn.close()


# ── ACTIVITY LOG ─────────────────────────────────────────────────────────────

def _log(c, candidate_id, candidate_name, action, details, performed_by):
    c.execute("""INSERT INTO activity_log (candidate_id, candidate_name, action, details, performed_by)
                 VALUES (?, ?, ?, ?, ?)""",
              (candidate_id, candidate_name, action, details, performed_by))


def log_activity(candidate_id, candidate_name, action, details, performed_by="System"):
    conn = get_connection()
    c = conn.cursor()
    _log(c, candidate_id, candidate_name, action, details, performed_by)
    conn.commit()
    conn.close()


def get_activity_log(candidate_id=None, limit=50):
    conn = get_connection()
    c = conn.cursor()
    if candidate_id:
        c.execute("SELECT * FROM activity_log WHERE candidate_id = ? ORDER BY created_at DESC LIMIT ?",
                  (candidate_id, limit))
    else:
        c.execute("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = rows_to_dicts(c.fetchall())
    conn.close()
    return rows


# ── ANALYTICS ────────────────────────────────────────────────────────────────

def get_analytics_data():
    conn = get_connection()
    c = conn.cursor()
    data = {}
    c.execute("SELECT stage, COUNT(*) as count FROM candidates GROUP BY stage")
    data['stage_dist'] = {r['stage']: r['count'] for r in c.fetchall()}
    c.execute("SELECT source, COUNT(*) as count FROM candidates GROUP BY source")
    data['source_dist'] = {r['source']: r['count'] for r in c.fetchall()}
    c.execute("SELECT score_band, COUNT(*) as count FROM candidates WHERE score_band != 'Unscored' GROUP BY score_band")
    data['score_dist'] = {r['score_band']: r['count'] for r in c.fetchall()}
    c.execute("""SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
                 FROM candidates GROUP BY month ORDER BY month DESC LIMIT 6""")
    data['monthly'] = rows_to_dicts(c.fetchall())
    conn.close()
    return data
