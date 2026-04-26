import random
import pandas as pd
from faker import Faker
<<<<<<< Updated upstream

fake = Faker()

=======
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

fake = Faker()

USE_REAL_APIFY = os.getenv("APIFY_TOKEN") is not None and os.getenv("APIFY_TOKEN").strip() != ""
APIFY_ACTOR_ID = "harvestapi/linkedin-profile-search"

>>>>>>> Stashed changes
SKILLS_POOL = {
    "AWS Data Engineer": ["AWS", "S3", "Glue", "Redshift", "Athena", "Lambda", "EMR", "Spark", "Python", "SQL", "Airflow", "Kafka", "Terraform", "Data Lake"],
    "Frontend Developer": ["React", "TypeScript", "JavaScript", "CSS", "HTML", "Next.js", "Redux", "GraphQL", "Tailwind", "Vue.js"],
    "DevOps Engineer": ["Docker", "Kubernetes", "CI/CD", "Jenkins", "Terraform", "AWS", "Azure", "Ansible", "Linux", "Prometheus"],
    "Data Scientist": ["Python", "ML", "TensorFlow", "PyTorch", "Pandas", "NumPy", "SQL", "Tableau", "Statistics", "NLP"],
    "Backend Developer": ["Python", "Java", "Node.js", "REST APIs", "PostgreSQL", "Redis", "Docker", "Microservices", "Spring Boot", "FastAPI"],
}

COMPANIES = ["Google", "Amazon", "Microsoft", "Meta", "Netflix", "Uber", "Airbnb", "Stripe", "Atlassian", "Canva", "Telstra", "Deloitte"]
LOCATIONS = ["Melbourne, VIC", "Sydney, NSW", "Brisbane, QLD", "Remote", "Perth, WA", "Adelaide, SA"]
HEADLINES = ["Senior {role} @ {company}", "{role} | {company}", "Lead {role} at {company}", "{role} @ {company} | {skill} specialist"]

<<<<<<< Updated upstream
HEADLINES = [
    "Senior {role} @ {company}",
    "{role} | {company}",
    "Lead {role} at {company}",
    "Principal {role} | Open to opportunities",
    "{role} @ {company} | {skill} specialist",
]


def generate_candidates(job_title: str, count: int = 20) -> pd.DataFrame:
=======
def generate_candidates(job_title: str, count: int = 20, location: str = "", mandatory_skills: str = "", desirable_skills: str = "") -> pd.DataFrame:
    """Main entry point. Uses real Apify scraping or falls back to mock data."""
    print(f"[generate_candidates] USE_REAL_APIFY={USE_REAL_APIFY}, job_title={job_title}, count={count}")
    
    if USE_REAL_APIFY:
        try:
            print("[generate_candidates] Attempting Apify fetch...")
            result = _fetch_from_apify(job_title, count, location, mandatory_skills, desirable_skills)
            return result
        except Exception as e:
            print(f"[Apify] ERROR: {e}")
            print("[generate_candidates] Falling back to mock data due to Apify error")
            return _generate_mock(job_title, count, mandatory_skills, desirable_skills)
            
    print("[generate_candidates] Using mock data (no Apify token)")
    return _generate_mock(job_title, count, mandatory_skills, desirable_skills)

# ─────────────────────────────────────────────
# REAL: Apify LinkedIn scraper
# ─────────────────────────────────────────────

def _fetch_from_apify(job_title: str, count: int, location: str = "", mandatory_skills: str = "", desirable_skills: str = "") -> pd.DataFrame:
    token = os.getenv("APIFY_TOKEN")
    client = ApifyClient(token)

    query_parts = [f'"{job_title}"']
    
    # Only force LinkedIn to search for the Mandatory skills
    if mandatory_skills and mandatory_skills.strip():
        skill_list = [s.strip() for s in mandatory_skills.split(",") if s.strip()]
        if skill_list:
            skills_formatted = " OR ".join(f'"{s}"' for s in skill_list)
            query_parts.append(f'({skills_formatted})')

    final_query = " AND ".join(query_parts)

    run_input = {
        "query": final_query,        
        "locations": [location] if location else [],
        "maxItems": count,
        "scrapeType": "short",
    }

    print(f"[Apify] Searching Title + Mandatory Skills: {final_query}")
    run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    
    print(f"[Apify] Got {len(items)} raw results")
    return _map_apify_to_schema(items, job_title, mandatory_skills, desirable_skills)

def _map_apify_to_schema(items: list, job_title: str, mandatory: str = "", desirable: str = "") -> pd.DataFrame:
    candidates = []
    for item in items:
        years_exp = _estimate_years_experience(item)
        skills = _extract_skills(item)
        scores = _calculate_skill_scores(skills, mandatory, desirable)

        current_company = item.get("currentCompany") or item.get("company") or "Unknown"
        first = item.get("firstName", "") or ""
        last = item.get("lastName", "") or ""
        name = f"{first} {last}".strip() or item.get("fullName", "") or "Unknown"

        candidates.append({
            "name": name,
            "headline": (item.get("headline") or item.get("title") or f"{job_title} Professional")[:100],
            "location": item.get("location") or "Unknown",
            "years_experience": years_exp,
            "current_company": str(current_company)[:50],
            "skills": skills,
            "skill_match_pct": scores["overall_pct"],
            "mandatory_match_pct": scores["mandatory_pct"],
            "desirable_match_pct": scores["desirable_pct"],
            "linkedin_url": item.get("linkedInUrl") or item.get("profileUrl") or "",
            "email": item.get("email", ""),
            "connections": item.get("connectionsCount") or item.get("connections") or 0,
            "ai_score": None,
            "ai_reasoning": None,
            "status": "New",
            "notes": "",
        })

    return pd.DataFrame(candidates) if candidates else _generate_mock(job_title, 10, mandatory, desirable)

# ─────────────────────────────────────────────
# MOCK: Fallback data generator
# ─────────────────────────────────────────────

def _generate_mock(job_title: str, count: int = 20, mandatory_skills: str = "", desirable_skills: str = "") -> pd.DataFrame:
>>>>>>> Stashed changes
    skills_pool = SKILLS_POOL.get(job_title, SKILLS_POOL["AWS Data Engineer"])
    candidates = []

    for _ in range(count):
        years_exp = random.randint(1, 15)
        num_skills = random.randint(4, 10)
        candidate_skills = random.sample(skills_pool, min(num_skills, len(skills_pool)))
        skills_str = ", ".join(candidate_skills)
        
        scores = _calculate_skill_scores(skills_str, mandatory_skills, desirable_skills)
        company = random.choice(COMPANIES)
        
        headline = random.choice(HEADLINES).format(
            role=job_title,
            company=company,
            skill=random.choice(candidate_skills) if candidate_skills else "Expert",
        )

        candidates.append({
            "name": fake.name(),
            "headline": headline,
            "location": random.choice(LOCATIONS),
            "years_experience": years_exp,
            "current_company": company,
            "skills": skills_str,
            "skill_match_pct": scores["overall_pct"],
            "mandatory_match_pct": scores["mandatory_pct"],
            "desirable_match_pct": scores["desirable_pct"],
            "linkedin_url": f"https://linkedin.com/in/{fake.user_name()}",
            "email": fake.email(),
            "connections": random.randint(200, 5000),
            "ai_score": None,
            "ai_reasoning": None,
            "status": "New",
            "notes": "",
        })

    return pd.DataFrame(candidates)
<<<<<<< Updated upstream
=======

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _calculate_skill_scores(candidate_skills_str: str, mandatory_str: str, desirable_str: str) -> dict:
    cand_skills = (candidate_skills_str or "").lower()
    
    req_skills = [s.strip().lower() for s in (mandatory_str or "").split(",") if s.strip()]
    mandatory_pct = int((sum(1 for skill in req_skills if skill in cand_skills) / len(req_skills)) * 100) if req_skills else 0

    nice_skills = [s.strip().lower() for s in (desirable_str or "").split(",") if s.strip()]
    desirable_pct = int((sum(1 for skill in nice_skills if skill in cand_skills) / len(nice_skills)) * 100) if nice_skills else 0

    overall_pct = int((mandatory_pct * 0.7) + (desirable_pct * 0.3)) if req_skills and nice_skills else mandatory_pct or desirable_pct

    return {"mandatory_pct": mandatory_pct, "desirable_pct": desirable_pct, "overall_pct": overall_pct}

def _estimate_years_experience(item: dict) -> int:
    experiences = item.get("experiences", [])
    if not experiences: return random.randint(2, 8)
    total_months = 0
    for exp in experiences:
        start = exp.get("startYear") or exp.get("start", {})
        end = exp.get("endYear") or exp.get("end", {})
        start_year = start.get("year") if isinstance(start, dict) else start if isinstance(start, int) else None
        end_year = end.get("year") if isinstance(end, dict) else end if isinstance(end, int) else 2025
        if start_year: total_months += (end_year - start_year) * 12
    return max(1, round(total_months / 12))

def _extract_skills(item: dict) -> str:
    skills_raw = item.get("skills", [])
    if skills_raw and isinstance(skills_raw, list):
        skill_names = [s.get("name", "") if isinstance(s, dict) else s for s in skills_raw[:10]]
        skill_names = [s for s in skill_names if s]
        if skill_names: return ", ".join(skill_names)

    summary = item.get("summary", "") or item.get("headline", "") or ""
    tech_keywords = ["Python", "Java", "AWS", "SQL", "React", "Docker", "Kubernetes", "Spark", "Airflow", "TensorFlow", "Node.js", "TypeScript"]
    found = [kw for kw in tech_keywords if kw.lower() in summary.lower()]
    return ", ".join(found) if found else "Not listed"
>>>>>>> Stashed changes
