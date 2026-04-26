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

    # Build LinkedIn people search URL
    query = job_title.replace(" ", "%20")
    loc = location.replace(" ", "%20") if location else ""
    search_url = f"https://www.linkedin.com/search/results/people/?keywords={query}"
    if loc:
        search_url += f"&location={loc}"

    run_input = {
        "query": job_title,           # general fuzzy search query
        "jobTitles": [job_title],     # exact job title filter
        "locations": [location] if location else [],
        "maxItems": count,
        "scrapeType": "short",
    }

    print(f"[Apify] Starting actor run for: {job_title} ({count} results)...")
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

        # harvestapi field names
        current_company = (
            item.get("currentCompany") or
            item.get("company") or
            item.get("currentPosition", {}).get("companyName", "") or
            "Unknown"
        )

        first = item.get("firstName", "") or ""
        last = item.get("lastName", "") or ""
        name = f"{first} {last}".strip() or item.get("fullName", "") or item.get("name", "Unknown")

        linkedin_url = (
            item.get("linkedInUrl") or
            item.get("profileUrl") or
            item.get("url") or
            ""
        )

        candidates.append({
            "name": name,
            "headline": (item.get("headline") or item.get("title") or f"{job_title} Professional")[:100],
            "location": item.get("location") or item.get("city") or "Unknown",
            "years_experience": years_exp,
            "current_company": str(current_company)[:50],
            "skills": skills,
            "linkedin_url": linkedin_url,
            "email": item.get("email", ""),
            "connections": item.get("connectionsCount") or item.get("connections") or 0,
            "ai_score": None,
            "ai_reasoning": None,
            "status": "New",
            "notes": "",
        })

    return pd.DataFrame(candidates) if candidates else _generate_mock(job_title, 10)


def _estimate_years_experience(item: dict) -> int:
    """Try to estimate years of experience from the profile data."""
    experiences = item.get("experiences", [])
    if not experiences:
        return random.randint(2, 8)

    total_months = 0
    for exp in experiences:
        start = exp.get("startYear") or exp.get("start", {})
        end = exp.get("endYear") or exp.get("end", {})

        start_year = None
        end_year = None

        if isinstance(start, dict):
            start_year = start.get("year")
        elif isinstance(start, int):
            start_year = start

        if isinstance(end, dict):
            end_year = end.get("year")
        elif isinstance(end, int):
            end_year = end

        if start_year:
            end_year = end_year or 2025
            total_months += (end_year - start_year) * 12

    return max(1, round(total_months / 12))


def _extract_skills(item: dict) -> str:
    """Extract skills from profile data."""
    # Try skills field first
    skills_raw = item.get("skills", [])
    if skills_raw and isinstance(skills_raw, list):
        skill_names = []
        for s in skills_raw[:10]:
            if isinstance(s, dict):
                skill_names.append(s.get("name", ""))
            elif isinstance(s, str):
                skill_names.append(s)
        skill_names = [s for s in skill_names if s]
        if skill_names:
            return ", ".join(skill_names)

    # Fall back to extracting from headline/summary
    summary = item.get("summary", "") or item.get("headline", "") or ""
    tech_keywords = [
        "Python", "Java", "AWS", "SQL", "React", "Docker", "Kubernetes",
        "Spark", "Airflow", "TensorFlow", "Node.js", "TypeScript", "Terraform",
        "Kafka", "Redshift", "PostgreSQL", "MongoDB", "Redis", "Golang",
    ]
    found = [kw for kw in tech_keywords if kw.lower() in summary.lower()]
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