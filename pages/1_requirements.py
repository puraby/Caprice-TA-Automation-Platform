import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from storage import load_requirements, save_requirements

ROLE_OPTIONS = [
    "AWS Data Engineer",
    "Frontend Developer",
    "DevOps Engineer",
    "Data Scientist",
    "Backend Developer",
    "Custom...",
]

SKILL_PRESETS = {
    "AWS Data Engineer": "AWS, S3, Glue, Redshift, Python, Spark, SQL, Airflow",
    "Frontend Developer": "React, TypeScript, CSS, Next.js, GraphQL",
    "DevOps Engineer": "Docker, Kubernetes, Terraform, CI/CD, AWS",
    "Data Scientist": "Python, ML, TensorFlow, SQL, Statistics, Pandas",
    "Backend Developer": "Python, REST APIs, PostgreSQL, Docker, Microservices",
}

st.title("📋 Job Requirements")
st.caption("Define what you're looking for — the system will search and score candidates automatically.")

reqs_df = load_requirements()

with st.form("req_form", clear_on_submit=True):
    st.subheader("New Requirement")

    col1, col2 = st.columns(2)
    with col1:
        role_choice = st.selectbox("Job Title", ROLE_OPTIONS)
        if role_choice == "Custom...":
            job_title = st.text_input("Enter custom job title")
        else:
            job_title = role_choice

    with col2:
        location = st.text_input("Location", placeholder="e.g. Melbourne, VIC or Remote")

    default_skills = SKILL_PRESETS.get(job_title, "")
    
    # --- NEW: Split into Mandatory and Desirable text areas ---
    mandatory_skills = st.text_area(
        "Mandatory Skills (Must have, comma separated)",
        value=default_skills,
        height=60,
    )
    desirable_skills = st.text_area(
        "Desirable Skills (Nice to have, comma separated)",
        placeholder="e.g. Airflow, Terraform, Management experience...",
        height=60,
    )

    col3, col4 = st.columns(2)
    with col3:
        min_years = st.slider("Minimum Years Experience", 1, 15, 4)
    with col4:
        num_candidates = st.number_input("Candidates to Find", min_value=5, max_value=100, value=20, step=5)

    notes = st.text_area("Additional Notes", placeholder="e.g. Must have fintech experience, open to contractors...", height=60)

    submitted = st.form_submit_button("➕ Add Requirement", width='stretch', type="primary")

    if submitted and job_title:
        new_row = pd.DataFrame([{
            "id": str(uuid.uuid4())[:8],
            "job_title": job_title,
            "mandatory_skills": mandatory_skills,   # Save mandatory
            "desirable_skills": desirable_skills,   # Save desirable
            "min_years_exp": min_years,
            "location": location,
            "num_candidates": num_candidates,
            "notes": notes,
            "status": "Pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }])
        reqs_df = pd.concat([reqs_df, new_row], ignore_index=True)
        save_requirements(reqs_df)
        st.success(f"✅ Requirement added for **{job_title}**")
        st.rerun()

st.divider()
st.subheader(f"Active Requirements ({len(reqs_df)})")

if reqs_df.empty:
    st.info("No requirements yet. Add your first one above.")
    st.stop()

for _, row in reqs_df.iterrows():
    status_color = {"Pending": "🟡", "In Progress": "🔵", "Completed": "🟢"}.get(row.get("status", "Pending"), "🟡")
    with st.expander(f"{status_color} {row['job_title']} — {row.get('location', 'Any')} | {row['min_years_exp']}+ yrs | {row['num_candidates']} candidates"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Min Experience", f"{row['min_years_exp']} yrs")
        c2.metric("Candidates Needed", row['num_candidates'])
        c3.metric("Status", row.get("status", "Pending"))
        
        # --- NEW: Display the split skills safely (fallback for older saved data) ---
        saved_mandatory = row.get('mandatory_skills', row.get('required_skills', 'N/A'))
        st.markdown(f"**Mandatory Skills:** {saved_mandatory}")
        if pd.notna(row.get('desirable_skills')) and str(row.get('desirable_skills')).strip():
            st.markdown(f"**Desirable Skills:** {row['desirable_skills']}")
            
        if row.get("notes") and pd.notna(row.get("notes")):
            st.markdown(f"**Notes:** {row['notes']}")
        st.caption(f"Created: {row.get('created_at', 'N/A')} · ID: {row['id']}")

        col_a, col_b = st.columns(2)
        with col_a:
            new_status = st.selectbox("Update status", ["Pending", "In Progress", "Completed"], key=f"status_{row['id']}", index=["Pending", "In Progress", "Completed"].index(row.get("status", "Pending")))
            if new_status != row.get("status"):
                reqs_df.loc[reqs_df["id"] == row["id"], "status"] = new_status
                save_requirements(reqs_df)
                st.rerun()
        with col_b:
            if st.button("🗑️ Delete", key=f"del_{row['id']}"):
                reqs_df = reqs_df[reqs_df["id"] != row["id"]]
                save_requirements(reqs_df)
                st.rerun()