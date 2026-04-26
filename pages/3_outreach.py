import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from storage import load_candidates, save_candidates, load_outreach, save_outreach, load_requirements
from ai_scorer import generate_outreach_message


st.title("📨 Outreach Automation")
st.caption("Generate personalized messages and track your outreach pipeline.")

candidates_df = load_candidates()
outreach_df = load_outreach()
reqs_df = load_requirements()

if candidates_df.empty:
    st.info("No candidates yet. Go to Candidates to fetch and score some first.")
    st.stop()

req_map = {r["job_title"]: r for _, r in reqs_df.iterrows()} if not reqs_df.empty else {}

# --- Message generator ---
with st.container(border=True):
    st.subheader("✍️ Generate Outreach Messages")

    shortlisted = candidates_df[candidates_df["status"] == "Shortlisted"]
    if shortlisted.empty:
        st.warning("No shortlisted candidates. Go to Candidates and set some to **Shortlisted**.")
    else:
        candidate_options = {f"{r['name']} — {r['headline'][:50]}": r for _, r in shortlisted.iterrows()}
        selected_name = st.selectbox("Select candidate", list(candidate_options.keys()))
        selected_candidate = candidate_options[selected_name]
        job_spec = req_map.get(selected_candidate.get("job_title", ""), {
            "job_title": selected_candidate.get("job_title", "the role"),
            "required_skills": selected_candidate.get("skills", ""),
        })

        if st.button("🤖 Generate Personalized Message", type="primary"):
            with st.spinner("Crafting message..."):
                msg = generate_outreach_message(selected_candidate.to_dict(), job_spec)
            st.session_state["generated_message"] = msg
            st.session_state["message_candidate"] = selected_candidate.to_dict()

        if "generated_message" in st.session_state:
            st.text_area("Generated Message (edit before sending)", st.session_state["generated_message"], height=160, key="msg_edit")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("📋 Copy to Clipboard (manual send)", width='stretch'):
                    st.toast("Message ready — copy it manually from the box above!", icon="📋")
            with col2:
                if st.button("✅ Mark as Sent", type="primary", width='stretch'):
                    cand = st.session_state["message_candidate"]
                    new_row = pd.DataFrame([{
                        "candidate_name": cand["name"],
                        "linkedin_url": cand["linkedin_url"],
                        "email": cand["email"],
                        "job_title": cand.get("job_title", ""),
                        "message_sent": st.session_state.get("msg_edit", st.session_state["generated_message"]),
                        "follow_up_1": "",
                        "follow_up_2": "",
                        "connection_status": "Pending",
                        "reply_received": "No",
                        "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }])
                    outreach_df = pd.concat([outreach_df, new_row], ignore_index=True)
                    save_outreach(outreach_df)

                    candidates_df.loc[
                        candidates_df["name"] == cand["name"], "status"
                    ] = "Contacted"
                    save_candidates(candidates_df)

                    del st.session_state["generated_message"]
                    st.success(f"✅ Marked {cand['name']} as Contacted!")
                    st.rerun()

st.divider()

# --- Outreach pipeline ---
st.subheader("📊 Outreach Pipeline")

if outreach_df.empty:
    st.info("No outreach sent yet.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Sent", len(outreach_df))
col2.metric("Pending Reply", len(outreach_df[outreach_df["reply_received"] == "No"]))
col3.metric("Replied", len(outreach_df[outreach_df["reply_received"] == "Yes"]))
reply_rate = len(outreach_df[outreach_df["reply_received"] == "Yes"]) / len(outreach_df) * 100
col4.metric("Reply Rate", f"{reply_rate:.0f}%")

st.divider()

for _, row in outreach_df.iterrows():
    replied_icon = "✅" if row.get("reply_received") == "Yes" else "⏳"
    with st.expander(f"{replied_icon} {row['candidate_name']} — {row['job_title']} — Sent: {row['sent_at']}"):
        st.markdown(f"**Message sent:**\n\n{row['message_sent']}")
        st.markdown(f"[🔗 LinkedIn]({row['linkedin_url']}) · 📧 {row['email']}")

        col_a, col_b = st.columns(2)
        with col_a:
            conn_status = st.selectbox(
                "Connection status",
                ["Pending", "Connected", "Declined"],
                index=["Pending", "Connected", "Declined"].index(str(row.get("connection_status", "Pending"))),
                key=f"conn_{row['linkedin_url']}",
            )
        with col_b:
            replied = st.selectbox(
                "Reply received?",
                ["No", "Yes"],
                index=["No", "Yes"].index(str(row.get("reply_received", "No"))),
                key=f"reply_{row['linkedin_url']}",
            )

        if st.button("💾 Update", key=f"save_{row['linkedin_url']}"):
            outreach_df.loc[outreach_df["linkedin_url"] == row["linkedin_url"], "connection_status"] = conn_status
            outreach_df.loc[outreach_df["linkedin_url"] == row["linkedin_url"], "reply_received"] = replied
            if replied == "Yes":
                candidates_df.loc[candidates_df["linkedin_url"] == row["linkedin_url"], "status"] = "Replied"
                save_candidates(candidates_df)
            save_outreach(outreach_df)
            st.success("Updated!")
            st.rerun()