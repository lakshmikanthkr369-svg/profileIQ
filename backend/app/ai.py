"""AI scoring, suggestions, rewrite and fresher builder. Ported from the Streamlit app."""
import json
import anthropic
from .config import API_KEY, CLAUDE_MODEL
from .ai_errors import create_json_message

def score_resume(resume_text, jd):
    """ATS scoring that mirrors how real recruiters and ATS tools score resumes"""
    client = anthropic.Anthropic(api_key=API_KEY)
    msg = client.messages.create(model=CLAUDE_MODEL, max_tokens=1500,
        messages=[{"role":"user","content":f"""You are an ATS (Applicant Tracking System) scoring expert.

Score this resume against the job description the way real ATS tools do:

SCORING RULES:
1. Extract only the TOP 15-20 most important keywords from the JD (core skills, must-have tools, key responsibilities)
2. Do NOT extract every single word — focus on meaningful technical skills, tools, certifications, and key role requirements
3. Match keywords using INTELLIGENT matching — synonyms count, related terms count:
   - "test automation" matches "automation framework", "automated testing"
   - "CI/CD" matches "Jenkins", "GitHub Actions", "pipeline"
   - "Python" matches "Python-based", "Python/Pytest"
   - "QA" matches "quality assurance", "SDET", "test engineer"
4. Calculate score on a REALISTIC scale — a strong relevant resume should score 65-85, not 20-30
5. Formula: score = (matched_count / total_extracted_keywords) * 100

Return in EXACT format — no other text:

ATS_SCORE: [integer between 0-100]
MATCHED_KEYWORDS: [only keywords genuinely present in resume, comma separated]
MISSING_KEYWORDS: [only truly missing important keywords, comma separated, max 8]

Resume:
{resume_text}

Job Description:
{jd}"""}])
    raw = msg.content[0].text.strip()
    result = {"score": 0, "matched": [], "missing": []}
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("ATS_SCORE:"):
            try: result["score"] = int(''.join(c for c in line.split(":",1)[1] if c.isdigit()))
            except: pass
        elif line.startswith("MATCHED_KEYWORDS:"):
            result["matched"] = [k.strip() for k in line.split(":",1)[1].split(",") if k.strip()]
        elif line.startswith("MISSING_KEYWORDS:"):
            result["missing"] = [k.strip() for k in line.split(":",1)[1].split(",") if k.strip()]
    return result

def get_suggestions(resume_text, jd, score, missing_keywords):
    client = anthropic.Anthropic(api_key=API_KEY)

    if score >= 80:
        context = f"""This resume already scores {score}/100 — it's a strong match for the job description.
The candidate has most required keywords. DO NOT suggest adding keywords that are already present.

Focus suggestions ONLY on:
1. How to make the resume stand out beyond ATS — human reviewer appeal
2. Quantifying achievements with specific numbers/metrics if not already done
3. Strengthening the professional summary for impact
4. Interview preparation tips specific to this role
5. Any genuinely missing soft skills or domain knowledge from the JD

Missing keywords (if any): {', '.join(missing_keywords) if missing_keywords else 'None — full match!'}"""
    elif score >= 65:
        context = f"""This resume scores {score}/100 — a decent match but with room to improve.
Missing keywords: {', '.join(missing_keywords[:6]) if missing_keywords else 'None'}

Focus suggestions on:
1. Specific missing keywords to naturally incorporate
2. Bullet points that could be rewritten to better match JD language
3. Strengthening sections that are weak vs the JD requirements
4. Quantifying existing achievements
5. Skills section gaps"""
    else:
        context = f"""This resume scores {score}/100 — significant gaps exist vs the job description.
Missing keywords: {', '.join(missing_keywords[:8]) if missing_keywords else 'None'}

Focus suggestions on:
1. The most critical missing keywords to add immediately
2. Which sections need the most rewriting to match the JD
3. Whether the candidate's experience level matches the role
4. Core skills gaps that need to be addressed
5. Recommend using the AI Rewrite feature"""

    msg = client.messages.create(model=CLAUDE_MODEL, max_tokens=1000,
        messages=[{"role":"user","content":f"""{context}

Give exactly 5 specific, actionable suggestions.
Return ONLY numbered suggestions — no headers, no extra text:
1. [suggestion]
2. [suggestion]
3. [suggestion]
4. [suggestion]
5. [suggestion]

Resume: {resume_text}
Job Description: {jd}"""}])
    sugs = []
    for line in msg.content[0].text.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            s = line.split(".",1)[-1].strip()
            if s: sugs.append(s)
    return sugs

def do_rewrite(resume_text, jd):
    client = anthropic.Anthropic(api_key=API_KEY, timeout=300.0)
    msg = create_json_message(client, model=CLAUDE_MODEL, max_tokens=8192,
        messages=[{"role":"user","content":f"""You are an expert ATS resume optimizer. Your ONLY goal is to maximize the ATS keyword match score between this resume and the job description.

STEP 1 — Extract ALL important keywords from the Job Description:
Skills, tools, technologies, frameworks, methodologies, domain terms, certifications, soft skills.

STEP 2 — Rewrite the resume to include AS MANY of those keywords as possible by:
- Rewriting the Professional Summary to pack in JD keywords naturally
- Rewriting EVERY bullet point to include relevant JD keywords
- Expanding the Skills and Competencies sections with ALL matching JD keywords the candidate could plausibly have based on their experience
- Updating the title/headline to match JD terminology

HARD RULES (never break these):
1. Keep name, email, phone, location, years of experience EXACTLY as they appear
2. Keep job titles, company names, employment dates EXACTLY as they appear
3. Keep education, certifications, languages EXACTLY as they appear
4. Do NOT invent job titles, degrees, or certifications the candidate does not have
5. You MAY add relevant skills to the skills section if they are plausible given the candidate's experience level and domain
6. Rewrite bullets aggressively — every bullet must contain relevant JD keywords
7. The rewritten resume MUST score 80+ on ATS keyword matching

Return ONLY valid JSON — no markdown, no fences, no explanation:
{{"name":"string","title":"string","contact":"string","summary":"string","competencies":[{{"label":"string","value":"string"}}],"experience":[{{"title":"string","company":"string","dates":"string","bullets":["string"]}}],"skills":[{{"label":"string","value":"string"}}],"achievements":["string"],"education":"string","certifications":"string"}}

Resume:
{resume_text}

Job Description:
{jd}"""}])
    raw = msg.content[0].text.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"): raw = part; break
    start = raw.find("{"); end = raw.rfind("}") + 1
    if start == -1 or end <= start: raise ValueError("No JSON found")
    raw = raw[start:end]
    data = json.loads(raw)
    # Sanitize nulls
    def s(v, d): return v if v is not None else d
    data["name"] = s(data.get("name"), "")
    data["title"] = s(data.get("title"), "")
    data["contact"] = s(data.get("contact"), "")
    data["summary"] = s(data.get("summary"), "")
    data["education"] = s(data.get("education"), "")
    data["certifications"] = s(data.get("certifications"), "")
    data["competencies"] = [c for c in s(data.get("competencies"), []) if c and c.get("label") and c.get("value")]
    data["skills"] = [sk for sk in s(data.get("skills"), []) if sk and sk.get("label") and sk.get("value")]
    data["achievements"] = [a for a in s(data.get("achievements"), []) if a]
    cleaned_exp = []
    for job in s(data.get("experience"), []):
        if not job: continue
        cleaned_exp.append({
            "title": s(job.get("title"), ""),
            "company": s(job.get("company"), ""),
            "dates": s(job.get("dates"), ""),
            "bullets": [b for b in s(job.get("bullets"), []) if b]
        })
    data["experience"] = cleaned_exp
    return data

def build_fresher_resume(profile_data, jd):
    """Builds a resume from scratch for a fresher (no prior resume) using
    their education/projects/skills data, tailored to the job description.
    Returns the SAME JSON schema as do_rewrite() so make_docx/make_pdf and
    the preview all work unchanged. Academic projects are mapped into the
    'experience' list but the section is labeled PROJECTS, not WORK
    EXPERIENCE, to stay honest on the actual resume."""
    client = anthropic.Anthropic(api_key=API_KEY, timeout=300.0)

    projects_text = "\n".join(
        f"- {p.get('name','')}: {p.get('description','')}"
        for p in profile_data.get("projects", []) if p.get("name")
    ) or "None provided"
    certs_text = ", ".join(
        c.get("name", "") for c in profile_data.get("certifications", []) if c.get("name")
    ) or "None"

    msg = create_json_message(client, model=CLAUDE_MODEL, max_tokens=8192,
        messages=[{"role": "user", "content": f"""You are an expert resume writer helping a FRESHER (no prior work experience — a student/recent graduate) build their first resume, tailored to a specific job description, optimized for ATS keyword matching.

STEP 1 — Extract important keywords from the Job Description (skills, tools, technologies, frameworks, domain terms).

STEP 2 — Build a resume that naturally incorporates as many relevant keywords as possible by:
- Writing a Professional Summary that frames the candidate's education, skills and projects around the JD's needs
- Rewriting each academic project's description into 2-4 achievement-style bullet points that use relevant JD keywords, WITHOUT inventing outcomes/metrics the candidate didn't provide — infer reasonable, plausible detail from the project description given, don't fabricate specific numbers that weren't implied
- Organizing the skills section to highlight JD-relevant skills first

HARD RULES (never break these):
1. This candidate has NO WORK EXPERIENCE — do not invent jobs, companies, or job titles implying employment
2. Do NOT invent degrees, institutions, or certifications beyond what's given
3. Do NOT fabricate specific metrics/numbers for projects that weren't provided or clearly implied
4. Keep name, email, phone, degree, institute, university, year of passing EXACTLY as given
5. It is fine to include commonly-paired, plausible skills alongside the candidate's stated skills IF clearly appropriate for their stated skill set (e.g. if they list "Python" and the JD wants "REST APIs", it's fine to phrase skills to include API familiarity IF plausible — but never claim a specific certification or tool they never mentioned)

Return ONLY valid JSON — no markdown, no fences, no explanation. Use this EXACT schema:
{{"name":"string","title":"string (a suitable target job title based on the JD)","contact":"string (email | phone)","summary":"string","experience_heading":"PROJECTS","competencies":[{{"label":"string","value":"string"}}],"experience":[{{"title":"string (project name)","company":"Academic Project","dates":"string (leave blank if not known)","bullets":["string"]}}],"skills":[{{"label":"string","value":"string"}}],"achievements":[],"education":"string","certifications":"string"}}

Candidate details:
Name: {profile_data.get('full_name','')}
Email: {profile_data.get('email','')}
Phone: {profile_data.get('phone','')}
Degree: {profile_data.get('degree','')}
Institute: {profile_data.get('institute','')}
University: {profile_data.get('university','')}
Year of Passing: {profile_data.get('year_of_passing','')}
Key Skills: {profile_data.get('key_skills','')}

Academic Projects:
{projects_text}

Certifications: {certs_text}

Job Description:
{jd}"""}])

    raw = msg.content[0].text.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"): raw = part; break
    start = raw.find("{"); end = raw.rfind("}") + 1
    if start == -1 or end <= start: raise ValueError("No JSON found")
    raw = raw[start:end]
    data = json.loads(raw)

    def s(v, d): return v if v is not None else d
    data["name"] = s(data.get("name"), profile_data.get("full_name", ""))
    data["title"] = s(data.get("title"), "")
    data["contact"] = s(data.get("contact"), f"{profile_data.get('email','')} | {profile_data.get('phone','')}")
    data["summary"] = s(data.get("summary"), "")
    data["experience_heading"] = "PROJECTS"
    data["education"] = s(data.get("education"),
        f"{profile_data.get('degree','')}, {profile_data.get('institute','')}, {profile_data.get('university','')} — {profile_data.get('year_of_passing','')}")
    data["certifications"] = s(data.get("certifications"), certs_text if certs_text != "None" else "")
    data["competencies"] = [c for c in s(data.get("competencies"), []) if c and c.get("label") and c.get("value")]
    data["skills"] = [sk for sk in s(data.get("skills"), []) if sk and sk.get("label") and sk.get("value")]
    data["achievements"] = [a for a in s(data.get("achievements"), []) if a]
    cleaned_exp = []
    for proj in s(data.get("experience"), []):
        if not proj: continue
        cleaned_exp.append({
            "title": s(proj.get("title"), ""),
            "company": s(proj.get("company"), "Academic Project"),
            "dates": s(proj.get("dates"), ""),
            "bullets": [b for b in s(proj.get("bullets"), []) if b]
        })
    data["experience"] = cleaned_exp
