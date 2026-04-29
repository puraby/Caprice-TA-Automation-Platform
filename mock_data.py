import os
import random
import re
import pandas as pd
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

fake = Faker()

# --- Toggle this to True once you have your Apify token in .env ---
USE_REAL_APIFY = os.getenv("APIFY_TOKEN") is not None and os.getenv("APIFY_TOKEN") != ""

# The best free LinkedIn People scraper on Apify
APIFY_ACTOR_ID = "harvestapi/linkedin-profile-search"

SKILLS_POOL = {
    "AWS Data Engineer": ["AWS", "S3", "Glue", "Redshift", "Athena", "Lambda", "EMR", "Spark", "Python", "SQL", "Airflow", "Kafka", "Terraform", "Data Lake"],
    "Frontend Developer": ["React", "TypeScript", "JavaScript", "CSS", "HTML", "Next.js", "Redux", "GraphQL", "Tailwind", "Vue.js"],
    "DevOps Engineer": ["Docker", "Kubernetes", "CI/CD", "Jenkins", "Terraform", "AWS", "Azure", "Ansible", "Linux", "Prometheus"],
    "Data Scientist": ["Python", "ML", "TensorFlow", "PyTorch", "Pandas", "NumPy", "SQL", "Tableau", "Statistics", "NLP"],
    "Backend Developer": ["Python", "Java", "Node.js", "REST APIs", "PostgreSQL", "Redis", "Docker", "Microservices", "Spring Boot", "FastAPI"],
}

COMPANIES = [
    "Google", "Amazon", "Microsoft", "Meta", "Netflix", "Uber", "Airbnb",
    "Stripe", "Atlassian", "Canva", "Afterpay", "REA Group", "Seek",
    "Commonwealth Bank", "Westpac", "Telstra", "Optus", "Deloitte", "KPMG",
]

LOCATIONS = ["Melbourne, VIC", "Sydney, NSW", "Brisbane, QLD", "Remote", "Perth, WA", "Adelaide, SA"]

HEADLINES = [
    "Senior {role} @ {company}",
    "{role} | {company}",
    "Lead {role} at {company}",
    "Principal {role} | Open to opportunities",
    "{role} @ {company} | {skill} specialist",
]


def generate_candidates(job_title: str, count: int = 20, location: str = "") -> pd.DataFrame:
    """
    Main entry point. Uses real Apify scraping if APIFY_TOKEN is set in .env,
    otherwise falls back to mock data.
    """
    print(f"[generate_candidates] USE_REAL_APIFY={USE_REAL_APIFY}, job_title={job_title}, count={count}")
    if USE_REAL_APIFY:
        try:
            print("[generate_candidates] Attempting Apify fetch...")
            result = _fetch_from_apify(job_title, count, location)
            print(f"[generate_candidates] Apify returned {len(result)} rows")
            return result
        except Exception as e:
            print(f"[Apify] ERROR: {e}")
            import traceback
            traceback.print_exc()
            print("[generate_candidates] Falling back to mock data")
            return _generate_mock(job_title, count)
    print("[generate_candidates] Using mock data (no Apify token)")
    return _generate_mock(job_title, count)


# ─────────────────────────────────────────────
# REAL: Apify LinkedIn scraper
# ─────────────────────────────────────────────

def _fetch_from_apify(job_title: str, count: int, location: str = "") -> pd.DataFrame:
    from apify_client import ApifyClient

    token = os.getenv("APIFY_TOKEN")
    client = ApifyClient(token)

    run_input = {
        "currentJobTitles": [job_title],   # correct field per harvestapi docs
        "maxItems": count,
        "scrapeType": "short",
    }
    if location:
        run_input["locations"] = [location]

    print(f"[Apify] Starting actor run for: {job_title} ({count} results)...")
    print(f"[Apify] run_input: {run_input}")
    run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"[Apify] Got {len(items)} raw results")

    return _map_apify_to_schema(items, job_title)


def _map_apify_to_schema(items: list, job_title: str) -> pd.DataFrame:
    """Map raw Apify harvestapi LinkedIn profile fields to our candidate schema."""
    candidates = []

    print(f"[Apify] Mapping {len(items)} items. First item keys: {list(items[0].keys()) if items else 'none'}")

    for item in items:
        years_exp = _estimate_years_experience(item)
        skills = _extract_skills(item)

        # currentPosition is a LIST in harvestapi — grab first entry
        current_position = item.get("currentPosition") or []
        if isinstance(current_position, list) and current_position:
            current_position = current_position[0]
        elif not isinstance(current_position, dict):
            current_position = {}

        current_company = (
            current_position.get("companyName") or
            current_position.get("company") or
            item.get("currentCompany") or
            "Unknown"
        )

        # emails is also a list
        emails = item.get("emails") or []
        email = emails[0] if isinstance(emails, list) and emails else ""

        first = item.get("firstName", "") or ""
        last = item.get("lastName", "") or ""
        name = f"{first} {last}".strip() or item.get("name", "Unknown")

        linkedin_url = item.get("linkedinUrl") or item.get("profileUrl") or ""

        # location can be a string or dict
        location_raw = item.get("location") or ""
        if isinstance(location_raw, dict):
            location_raw = location_raw.get("name") or location_raw.get("city") or "Unknown"

        candidates.append({
            "name": name,
            "headline": str(item.get("headline") or f"{job_title} Professional")[:100],
            "location": str(location_raw)[:60],
            "years_experience": years_exp,
            "current_company": str(current_company)[:50],
            "skills": skills,
            "linkedin_url": linkedin_url,
            "email": str(email),
            "connections": item.get("connectionsCount") or 0,
            "ai_score": None,
            "ai_reasoning": None,
            "status": "New",
            "notes": "",
        })

    return pd.DataFrame(candidates) if candidates else _generate_mock(job_title, 10)


def _estimate_years_experience(item: dict) -> int:
    """Try to estimate years of experience from the profile data."""
    # harvestapi uses "experience" (not "experiences")
    experiences = item.get("experience") or item.get("experiences") or []
    if not experiences:
        return random.randint(2, 8)

    total_months = 0
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        # harvestapi date format: {"start": {"month": 1, "year": 2018}, "end": {...}}
        start = exp.get("start") or {}
        end = exp.get("end") or {}

        start_year = start.get("year") if isinstance(start, dict) else None
        end_year = end.get("year") if isinstance(end, dict) else None

        if start_year:
            end_year = end_year or 2026
            total_months += (end_year - start_year) * 12

    return max(1, round(total_months / 12)) if total_months > 0 else random.randint(2, 8)


def _extract_skills(item: dict) -> str:
    """Extract skills from harvestapi profile data."""
    # harvestapi provides "topSkills" and "skills" lists
    skill_names = []

    for field in ["topSkills", "skills"]:
        skills_raw = item.get(field) or []
        if isinstance(skills_raw, list):
            for s in skills_raw[:10]:
                if isinstance(s, dict):
                    name = s.get("name") or s.get("title") or ""
                elif isinstance(s, str):
                    name = s
                else:
                    name = ""
                if name:
                    skill_names.append(name)
        if skill_names:
            break

    if skill_names:
        return ", ".join(skill_names[:10])

    # Fallback: extract tech keywords from headline/about
    text = str(item.get("about") or item.get("headline") or "")
    tech_keywords = [
        "Python", "Java", "AWS", "SQL", "React", "Docker", "Kubernetes",
        "Spark", "Airflow", "TensorFlow", "Node.js", "TypeScript", "Terraform",
        "Kafka", "Redshift", "PostgreSQL", "MongoDB", "Redis", "Golang",
    ]
    found = [kw for kw in tech_keywords if kw.lower() in text.lower()]
    return ", ".join(found) if found else "Not listed"


# ─────────────────────────────────────────────
# MOCK: Fallback data generator
# ─────────────────────────────────────────────

def _generate_mock(job_title: str, count: int = 20) -> pd.DataFrame:
    skills_pool = SKILLS_POOL.get(job_title, SKILLS_POOL["AWS Data Engineer"])
    candidates = []

    for _ in range(count):
        years_exp = random.randint(1, 15)
        num_skills = random.randint(4, 10)
        candidate_skills = random.sample(skills_pool, min(num_skills, len(skills_pool)))
        company = random.choice(COMPANIES)
        headline_template = random.choice(HEADLINES)
        headline = headline_template.format(
            role=job_title,
            company=company,
            skill=random.choice(candidate_skills),
        )

        candidates.append({
            "name": fake.name(),
            "headline": headline,
            "location": random.choice(LOCATIONS),
            "years_experience": years_exp,
            "current_company": company,
            "skills": ", ".join(candidate_skills),
            "linkedin_url": f"https://linkedin.com/in/{fake.user_name()}",
            "email": fake.email(),
            "connections": random.randint(200, 5000),
            "ai_score": None,
            "ai_reasoning": None,
            "status": "New",
            "notes": "",
        })

    return pd.DataFrame(candidates)