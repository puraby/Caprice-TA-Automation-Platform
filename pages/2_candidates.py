import streamlit as st
import pandas as pd
import sys, os

# Load .env BEFORE importing mock_data so APIFY_TOKEN is available at module level
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from storage import load_candidates, save_candidates, load_requirements
from mock_data import generate_candidates
from ai_scorer import score_candidate

STATUS_OPTIONS = ["New", "Shortlisted", "Contacted", "Replied", "Interview", "Rejected"]
STATUS_COLORS = {
    "New": "🔵", "Shortlisted": "🟢", "Contacted": "🟡",
    "Replied": "🟠", "Interview": "⭐", "Rejected": "🔴",
}

apify_connected = bool(os.getenv("APIFY_TOKEN"))

st.title("🔍 Candidate Search & Scoring")

if apify_connected:
    st.success("🟢 Apify connected — fetching real LinkedIn profiles")
else:
    st.warning("🟡 Apify not connected — using mock data. Add `APIFY_TOKEN` to your `.env` file to enable real search.")

reqs_df = load_requirements()
candidates_df = load_candidates()

# --- Search panel ---
with st.container(border=True):
    st.subheader("Search Candidates")

    if reqs_df.empty:
        st.warning("No requirements found. Add requirements first.")
        st.stop()

    req_options = {f"{r['job_title']} ({r['id']})": r for _, r in reqs_df.iterrows()}
    selected_label = st.selectbox("Select a requirement to search for", list(req_options.keys()))
    selected_req = req_options[selected_label]

    col1, col2 = st.columns([3, 1])
    with col1:
        num = st.slider("Number of candidates to fetch", 5, 50, int(selected_req.get("num_candidates", 20)))
    with col2:
        st.metric("Min Exp", f"{selected_req['min_years_exp']} yrs")

    btn_label = "🔎 Search Real LinkedIn Profiles (Apify)" if apify_connected else "🔎 Fetch Mock Candidates"

    if st.button(btn_label, type="primary", use_container_width=True):
        location = str(selected_req.get("location", ""))

        # --- Debug panel ---
        debug = st.expander("🛠️ Debug log", expanded=True)
        debug.write(f"**Job title:** {selected_req['job_title']}")
        debug.write(f"**Location:** {location or 'Not set'}")
        debug.write(f"**Count:** {num}")
        debug.write(f"**Apify token found:** {bool(os.getenv('APIFY_TOKEN'))}")
        debug.write(f"**USE_REAL_APIFY:** {apify_connected}")

        with st.spinner("Searching LinkedIn profiles... this may take 30-60 seconds for real data"):
            try:
                import mock_data as md
                debug.write(f"**USE_REAL_APIFY in module:** {md.USE_REAL_APIFY}")

                if apify_connected:
                    debug.write("▶️ Calling Apify actor...")

                new_candidates = generate_candidates(
                    selected_req["job_title"],
                    count=num,
                    location=location,
                )
                debug.write(f"✅ Got **{len(new_candidates)}** candidates back")
                debug.write(f"**Sample name:** {new_candidates.iloc[0]['name'] if len(new_candidates) > 0 else 'none'}")
                debug.write(f"**Sample LinkedIn URL:** {new_candidates.iloc[0]['linkedin_url'] if len(new_candidates) > 0 else 'none'}")

                # If URL is a fake faker URL, it's mock data
                sample_url = str(new_candidates.iloc[0]["linkedin_url"]) if len(new_candidates) > 0 else ""
                if "linkedin.com/in/" in sample_url and len(sample_url) < 50:
                    debug.warning("⚠️ URLs look like mock data (short/fake). Apify may have fallen back.")
                else:
                    debug.success("✅ URLs look real!")

                new_candidates["job_title"] = selected_req["job_title"]
                candidates_df = pd.concat([candidates_df, new_candidates], ignore_index=True)
                save_candidates(candidates_df)
                source = "real LinkedIn" if apify_connected else "mock"
                st.success(f"Found {len(new_candidates)} {source} candidates for **{selected_req['job_title']}**")

            except Exception as e:
                st.error(f"❌ Error: {e}")
                debug.error(f"Full error: {e}")
                import traceback
                debug.code(traceback.format_exc())

        st.rerun()

st.divider()

if candidates_df.empty:
    st.info("No candidates yet. Run a search above.")
    st.stop()

# --- Filters ---
with st.expander("🔧 Filters", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_role = st.multiselect("Job Title", candidates_df["job_title"].dropna().unique().tolist())
    with col2:
        filter_status = st.multiselect("Status", STATUS_OPTIONS)
    with col3:
        min_score = st.slider("Min AI Score", 0, 100, 0)

filtered = candidates_df.copy()
if filter_role:
    filtered = filtered[filtered["job_title"].isin(filter_role)]
if filter_status:
    filtered = filtered[filtered["status"].isin(filter_status)]
if min_score > 0:
    filtered = filtered[pd.to_numeric(filtered["ai_score"], errors="coerce").fillna(0) >= min_score]

# --- Bulk AI scoring ---
unscored = filtered[filtered["ai_score"].isna()]
col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Total Candidates", len(filtered))
col_b.metric("Unscored", len(unscored))
scored = filtered[filtered["ai_score"].notna()]
col_c.metric("Avg Score", f"{pd.to_numeric(scored['ai_score'], errors='coerce').mean():.0f}" if not scored.empty else "—")

with col_d:
    if st.button("🗑️ Clear All Candidates", use_container_width=True):
        st.session_state["confirm_clear"] = True

if st.session_state.get("confirm_clear"):
    st.warning("⚠️ This will delete ALL candidates from the CSV. Are you sure?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Yes, delete all", type="primary", use_container_width=True):
            empty_df = pd.DataFrame(columns=candidates_df.columns)
            save_candidates(empty_df)
            st.session_state["confirm_clear"] = False
            st.success("All candidates cleared!")
            st.rerun()
    with c2:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state["confirm_clear"] = False
            st.rerun()

if not unscored.empty:
    if st.button(f"🤖 AI Score All {len(unscored)} Unscored Candidates", use_container_width=True):
        progress = st.progress(0, text="Scoring candidates...")
        req_map = {r["job_title"]: r for _, r in reqs_df.iterrows()}

        # Ensure columns are object dtype before setting string values
        candidates_df["ai_score"] = candidates_df["ai_score"].astype(object)
        candidates_df["ai_reasoning"] = candidates_df["ai_reasoning"].astype(object)

        for i, (idx, row) in enumerate(unscored.iterrows()):
            job_spec = req_map.get(row.get("job_title", ""), selected_req)
            result = score_candidate(row.to_dict(), job_spec)
            candidates_df.at[idx, "ai_score"] = result["score"]
            candidates_df.at[idx, "ai_reasoning"] = result["reasoning"]
            progress.progress((i + 1) / len(unscored), text=f"Scoring {row['name']}...")

        save_candidates(candidates_df)
        st.success("✅ All candidates scored!")
        st.rerun()

st.divider()

# --- Candidate cards ---
sorted_df = filtered.copy()
sorted_df["ai_score_num"] = pd.to_numeric(sorted_df["ai_score"], errors="coerce").fillna(-1)
sorted_df = sorted_df.sort_values("ai_score_num", ascending=False)

st.subheader(f"Candidates ({len(sorted_df)})")

for _, row in sorted_df.iterrows():
    score = row.get("ai_score")
    score_display = f"{int(float(score))}/100" if pd.notna(score) else "Not scored"
    score_color = "🟢" if pd.notna(score) and float(score) >= 75 else "🟡" if pd.notna(score) and float(score) >= 50 else "🔴" if pd.notna(score) else "⚪"
    status_icon = STATUS_COLORS.get(str(row.get("status", "New")), "🔵")

    with st.expander(f"{score_color} {score_display} · {row['name']} · {row['headline'][:60]}... {status_icon}"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("AI Score", score_display)
        c2.metric("Experience", f"{row['years_experience']} yrs")
        c3.metric("Company", str(row['current_company'])[:15])
        c4.metric("Location", str(row['location'])[:15])

        st.markdown(f"**Skills:** {row['skills']}")
        if pd.notna(row.get("ai_reasoning")):
            st.info(f"🤖 **AI Reasoning:** {row['ai_reasoning']}")

        col_link, col_status, col_note = st.columns([1, 1, 2])
        with col_link:
            st.markdown(f"[🔗 LinkedIn Profile]({row['linkedin_url']})")
            st.caption(f"📧 {row['email']}")
        with col_status:
            new_status = st.selectbox(
                "Status", STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(str(row.get("status", "New"))) if str(row.get("status", "New")) in STATUS_OPTIONS else 0,
                key=f"status_{row['linkedin_url']}_{row['name']}",
            )
            if new_status != row.get("status"):
                candidates_df.loc[
                    (candidates_df["name"] == row["name"]) &
                    (candidates_df["linkedin_url"] == row["linkedin_url"]),
                    "status"
                ] = new_status
                save_candidates(candidates_df)
                st.rerun()
        with col_note:
            note = st.text_input("Notes", value=str(row.get("notes", "")), key=f"note_{row['linkedin_url']}_{row['name']}", placeholder="Add a note...")
            if note != str(row.get("notes", "")):
                candidates_df.loc[
                    (candidates_df["name"] == row["name"]) &
                    (candidates_df["linkedin_url"] == row["linkedin_url"]),
                    "notes"
                ] = note
                save_candidates(candidates_df)