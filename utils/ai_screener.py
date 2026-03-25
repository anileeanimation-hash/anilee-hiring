"""
AI Screener — uses 'claude' CLI (Claude Code subscription) or Anthropic API key.
No separate API key needed if Claude Code is installed.
"""

import json
import os
import subprocess


def _get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    return key


def _find_claude_binary() -> str:
    """Find the claude CLI binary in known locations."""
    candidates = [
        "claude",
        os.path.expanduser("~/.claude/local/claude"),
        "/usr/local/bin/claude",
        os.path.expanduser("~/Library/Application Support/Claude/claude-code/2.1.78/claude.app/Contents/MacOS/claude"),
        os.path.expanduser("~/Library/Application Support/Claude/claude-code-vm/2.1.74/claude"),
    ]
    for c in candidates:
        try:
            r = subprocess.run([c, "--version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return "claude"


def _claude_via_cli(prompt: str) -> str:
    """Call Claude via the 'claude' CLI — uses existing Claude Code subscription."""
    try:
        binary = _find_claude_binary()
        result = subprocess.run(
            [binary, "-p", prompt],
            capture_output=True, text=True, timeout=90,
            env={**os.environ, "NO_COLOR": "1"}
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"CLI error: {e}")
    return ""


def _claude_via_api(prompt: str) -> str:
    """Call Claude via API key (if configured)."""
    api_key = _get_api_key()
    if not api_key:
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5",  # Cheapest model for screening
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"API error: {e}")
        return ""


def _call_claude(prompt: str) -> str:
    """Call Claude via API first, then fall back to CLI."""
    # Try API key first (faster)
    if _get_api_key():
        result = _claude_via_api(prompt)
        if result:
            return result
    # Fall back to CLI (uses Claude Code subscription)
    result = _claude_via_cli(prompt)
    if result:
        return result
    return ""


def _parse_json(text: str) -> dict:
    """Extract JSON from Claude response."""
    if not text:
        return {}
    # Strip markdown code fences
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            if p.startswith("json"):
                text = p[4:]
                break
            elif "{" in p:
                text = p
                break
    text = text.strip()
    # Find first { ... }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            pass
    return {}


def _rule_based_score_response(question: str, response_text: str,
                                is_hard_filter: bool) -> tuple[int, str]:
    """Rule-based fallback scorer when AI is unavailable."""
    t = response_text.strip().lower()
    q = question.lower()

    if is_hard_filter:
        # Yes/No hard filters — check for positive/negative answer
        positive = ["yes", "ho", "ahe", "hoy", "haa", "haan", "available", "ready",
                    "can", "will", "sure", "definitely", "absolutely", "agree"]
        negative = ["no", "nahi", "naahi", "not", "cannot", "can't", "won't",
                    "unable", "unavailable", "no i"]
        t_clean = t.replace("'", "").replace(",", "")
        is_positive = any(t_clean.startswith(p) or f" {p}" in t_clean or t_clean == p
                          for p in positive)
        is_negative = any(t_clean.startswith(n) or t_clean == n for n in negative)
        if is_negative and not is_positive:
            return 0, "Candidate answered negatively."
        return 10, "Candidate confirmed requirement."

    # Soft question — score 0-10 based on response quality + keywords
    score = 0

    # 1. Response length / effort (0-4 pts)
    words = len(t.split())
    if words >= 40:
        score += 4
    elif words >= 20:
        score += 3
    elif words >= 10:
        score += 2
    elif words >= 4:
        score += 1

    # 2. Sales / counselling keywords (0-3 pts)
    sales_kw = ["sales", "target", "lead", "conversion", "counsell", "admission",
                "enroll", "achieve", "close", "pitch", "followup", "follow up",
                "client", "customer", "revenue", "incentive"]
    hits = sum(1 for k in sales_kw if k in t)
    score += min(hits, 3)

    # 3. Experience / numbers mentioned (0-2 pts)
    import re
    has_numbers = bool(re.search(r'\d+', t))
    exp_kw = ["year", "month", "experience", "worked", "job", "company", "institute",
              "academy", "school", "college"]
    has_exp = any(k in t for k in exp_kw)
    if has_numbers and has_exp:
        score += 2
    elif has_numbers or has_exp:
        score += 1

    # 4. Salary / availability / location (0-1 pt)
    bonus_kw = ["satara", "sangli", "kolhapur", "15000", "20000", "25000",
                "immediately", "join", "₹", "rs ", "lakh", "salary"]
    if any(k in t for k in bonus_kw):
        score += 1

    score = min(10, max(1, score))
    feedback = f"Rule-based score ({words} words). AI scoring unavailable — review manually."
    return score, feedback


def score_response(question: str, response_text: str, category: str,
                   is_hard_filter: bool, weight: int) -> tuple[int, str]:
    """Score a single candidate response. Returns (score 0-10, feedback)."""
    if not response_text or not response_text.strip():
        return 0, "No response provided."

    if is_hard_filter:
        prompt = f"""You are screening for Educational Counsellor at Anilee Academy, Satara, Maharashtra.

Hard Filter: {question}
Candidate Answer: {response_text}

PASS if the answer is positive/yes/confirms the requirement. FAIL only if clearly negative.
Reply ONLY with JSON: {{"pass": 1, "reason": "one short line"}}"""
    else:
        prompt = f"""You are scoring a candidate for Educational Counsellor at Anilee Academy — an animation & skill institute in Satara, Maharashtra.

Ideal candidate: persuasive, sales-driven, target-oriented, resilient, experienced in lead conversion. Salary: ₹15,000–₹25,000/month.

Category: {category}
Question: {question}
Answer: {response_text}

Score 0–10:
0-3 = Poor (vague, no sales aptitude)
4-6 = Average (some experience, not impressive)
7-8 = Good (clear sales mindset, solid answer)
9-10 = Excellent (exceptional, strong fit)

Reply ONLY with JSON: {{"score": <0-10>, "feedback": "<1-2 sentences>"}}"""

    text = _call_claude(prompt)
    result = _parse_json(text)

    if not result:
        return _rule_based_score_response(question, response_text, is_hard_filter)

    if is_hard_filter:
        score = 10 if int(result.get("pass", 0)) == 1 else 0
        return score, result.get("reason", "")
    else:
        score = min(10, max(0, int(result.get("score", 5))))
        return score, result.get("feedback", "")


def _rule_based_score_full(candidate_name: str, email_body: str,
                           enabled_questions: list) -> tuple[int, str, str, bool]:
    """Rule-based full-form scorer when AI is unavailable. Returns (score, band, summary, hard_fail)."""
    import re
    t = email_body.lower()
    score = 0
    hard_fail = False
    flags = []

    # ── Hard filter checks ────────────────────────────────────────────────────
    # Location check
    location_kw = ["satara", "sangli", "kolhapur", "ichalkaranji", "karad",
                   "miraj", "nearby", "local", "same city"]
    neg_location = ["not in satara", "nahi rahato", "other city", "pune", "mumbai",
                    "delhi", "bangalore", "chennai", "hyderabad"]
    if any(k in t for k in neg_location):
        hard_fail = True
        flags.append("Location mismatch")
    elif any(k in t for k in location_kw):
        score += 15

    # Marathi check
    marathi_pos = ["marathi", "ho", "hoy", "ahe", "ahet", "bolto", "boltoy"]
    if any(k in t for k in marathi_pos):
        score += 10

    # ── Experience scoring ────────────────────────────────────────────────────
    exp_numbers = re.findall(r'(\d+)\s*(year|yr|month|mahina)', t)
    if exp_numbers:
        num, unit = exp_numbers[0]
        months = int(num) * 12 if "year" in unit or "yr" in unit else int(num)
        if months >= 24:
            score += 20
        elif months >= 12:
            score += 15
        elif months >= 3:
            score += 10
        else:
            score += 3
    else:
        exp_kw = ["experience", "worked", "job", "company", "sales", "counselling",
                  "admission", "bde", "executive", "intern"]
        if any(k in t for k in exp_kw):
            score += 8

    # ── Sales aptitude keywords ───────────────────────────────────────────────
    sales_kw = ["target", "lead", "conversion", "close", "achieve", "pitch",
                "follow", "enroll", "client", "revenue", "incentive", "cold call"]
    hits = sum(1 for k in sales_kw if k in t)
    score += min(hits * 4, 20)

    # ── Response quality / effort ─────────────────────────────────────────────
    words = len(t.split())
    if words >= 150:
        score += 15
    elif words >= 80:
        score += 10
    elif words >= 40:
        score += 7
    elif words >= 15:
        score += 3

    # ── Salary in reasonable range ────────────────────────────────────────────
    salary_nums = re.findall(r'(\d{4,6})', t)
    for s in salary_nums:
        val = int(s)
        if 12000 <= val <= 30000:
            score += 5
            break
        elif val > 50000:
            score -= 5  # Unrealistic expectation

    # ── Availability ─────────────────────────────────────────────────────────
    avail_kw = ["immediately", "join", "available", "notice", "week", "days"]
    if any(k in t for k in avail_kw):
        score += 5

    score = min(95, max(0, score))

    if hard_fail:
        return 0, "Rejected ❌", f"{candidate_name} failed location/hard filter (rule-based check).", True

    band = "Hot 🔥" if score >= 80 else ("Warm ✅" if score >= 60 else ("Cold ❄️" if score >= 40 else "Rejected ❌"))
    flags_txt = f" Notes: {', '.join(flags)}." if flags else ""
    summary = (f"{candidate_name} scored {score}% via rule-based analysis ({words} words).{flags_txt} "
               f"AI scoring unavailable on cloud — manual review recommended.")
    return score, band, summary, False


def score_email_reply(candidate_name: str, email_body: str,
                       enabled_questions: list) -> tuple[int, str, str, bool]:
    """
    Score a candidate's email reply against the screening questions.
    Returns (final_score, score_band, ai_summary, hard_filter_failed)
    """
    prompt = f"""You are an HR AI for Anilee Academy (animation institute, Satara, Maharashtra).
A candidate replied to the screening email. Evaluate their reply.

Candidate: {candidate_name}
Email Reply:
---
{email_body[:2000]}
---

Screening Questions Asked:
{chr(10).join([f"{i+1}. {q['question']}" for i, q in enumerate(enabled_questions[:8])])}

Hard Filters (must pass all):
- Based in Satara/nearby area
- Marathi speaker
- At least 3 months sales/counselling experience

Score the overall reply 0-100. Check if any hard filter clearly fails.

Reply ONLY with JSON:
{{
  "score": <0-100>,
  "hard_filter_failed": <true/false>,
  "failed_filter": "<which filter failed, or empty>",
  "score_band": "<Hot/Warm/Cold/Rejected>",
  "summary": "<3 sentences: sales aptitude, experience, overall recommendation>",
  "response_quality": "<good/partial/poor>"
}}

Score bands: Hot=80+, Warm=60-79, Cold=40-59, Rejected=below 40 or hard filter fail"""

    text = _call_claude(prompt)
    result = _parse_json(text)

    if not result:
        return _rule_based_score_full(candidate_name, email_body, enabled_questions)

    score = min(100, max(0, int(result.get("score", 50))))
    hard_fail = bool(result.get("hard_filter_failed", False))
    summary = result.get("summary", f"{candidate_name} completed screening.")

    if hard_fail:
        return 0, "Rejected ❌", f"Failed hard filter: {result.get('failed_filter', 'unknown')}. {summary}", True

    raw_band = result.get("score_band", "")
    if "hot" in raw_band.lower():
        band = "Hot 🔥"
    elif "warm" in raw_band.lower():
        band = "Warm ✅"
    elif "cold" in raw_band.lower():
        band = "Cold ❄️"
    else:
        band = "Rejected ❌" if score < 40 else ("Cold ❄️" if score < 60 else ("Warm ✅" if score < 80 else "Hot 🔥"))

    return score, band, summary, False


def evaluate_full_screening(candidate_name: str, responses_data: list) -> tuple[int, str, str, bool]:
    """Evaluate complete screening from manual Q&A. Returns (score, band, summary, failed)."""
    hard_filters = [r for r in responses_data if r.get("is_hard_filter")]
    for hf in hard_filters:
        if hf.get("ai_score", 0) == 0 and hf.get("response", "").strip():
            return 0, "Rejected ❌", f"{candidate_name} failed mandatory check: {hf['question']}", True

    soft = [r for r in responses_data if not r.get("is_hard_filter") and r.get("response", "").strip()]
    if not soft:
        return 50, "Warm ✅", f"{candidate_name} passed hard filters. No soft scoring done.", False

    total = sum(r.get("ai_score", 0) * r.get("weight", 1) for r in soft)
    max_pts = sum(10 * r.get("weight", 1) for r in soft)
    score = int((total / max(max_pts, 1)) * 100)

    band = "Hot 🔥" if score >= 80 else ("Warm ✅" if score >= 60 else ("Cold ❄️" if score >= 40 else "Rejected ❌"))

    # Generate summary
    qa_text = "\n".join([
        f"Q: {r['question']}\nA: {r['response']}\nScore: {r.get('ai_score', '?')}/10"
        for r in responses_data if r.get("response", "").strip()
    ])
    summary_prompt = f"""Write a 3-sentence HR summary for {candidate_name} (score: {score}%, {band}).
Focus on sales aptitude, experience, fit for Educational Counsellor role.
Q&A: {qa_text[:1500]}
Be direct and actionable. 3rd person."""
    summary = _call_claude(summary_prompt) or f"{candidate_name} scored {score}% ({band})."

    return score, band, summary, False


def get_whatsapp_template(candidate_name: str = "[Candidate Name]") -> str:
    return f"""Namaste {candidate_name}! 🙏

*Anilee Academy, Satara* madhun bolat ahe.

Aapan *Educational Counsellor* sathi apply kele aahe. Aapla profile interesting vatalay. Pudhe process sathi kahi short questions aahet.

Please ya questions cha answer dya:

1. Sध्या Satara / nearby mdhye rahata ka? (ho/nahi)
2. Marathi fluent bolata ka? (ho/nahi)
3. Sales/counselling/admissions madhe kitna experience?
4. Magil role madhe per week kitne leads handle kelat?
5. Expected salary (₹ madhe)?
6. Join karne sathi kitne days lagel?

✅ Shortlisted candidates la direct *HR interview call* milel.

— HR Team, Anilee Academy 🎓"""
