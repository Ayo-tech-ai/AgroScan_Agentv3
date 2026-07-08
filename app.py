import streamlit as st
import sqlite3
import pandas as pd
import asyncio

from agroscan.database import (
    DATABASE_NAME,
    EXCEL_FILE,
    create_farm_records_table,
    initialize_farm_record_book,
    get_record_count,
)
from agroscan.agent import build_agent_system


# ============================================================
# PAGE CONFIG — must be the first Streamlit command in the script
# ============================================================
st.set_page_config(
    page_title="AgroScan AI Farm Manager",
    page_icon="🐔",
    layout="centered"
)


# ============================================================
# DATABASE INITIALIZATION
# Runs on every script rerun, but the Excel import only actually
# executes once per container cold start (guarded by record
# count). The database lives at the CONTAINER level, shared by
# every visitor until the container restarts (Path A: known,
# accepted trade-off — data does not survive a redeploy/sleep).
# ============================================================

create_farm_records_table()

if get_record_count() == 0:
    _imported, _skipped = initialize_farm_record_book(EXCEL_FILE)
    st.session_state.import_summary = (
        f"Imported {_imported} historical records "
        f"({_skipped} skipped as duplicates)."
    )
else:
    st.session_state.setdefault("import_summary", None)


# ============================================================
# ONE-TIME AGENT/RUNNER SETUP
# Only runs once per browser session — everything is then stored
# in st.session_state and reused on every subsequent rerun
# (i.e. every message sent), rather than rebuilt from scratch.
# ============================================================

if "initialized" not in st.session_state:
    st.session_state.initialized = False

if not st.session_state.initialized:

    groq_api_key = st.secrets["GROQ_API_KEY"]

    agent_system = build_agent_system(groq_api_key)

    st.session_state.runner = agent_system["runner"]
    st.session_state.session_service = agent_system["session_service"]
    st.session_state.agroscan_session = agent_system["session"]
    st.session_state.user_id = agent_system["user_id"]
    st.session_state.chat_history = []

    st.session_state.initialized = True


# ============================================================
# ASYNC BRIDGE
# runner.run_debug(...) is async; Streamlit's script executes
# synchronously, so this wraps the call.
# ============================================================

def run_agent_turn(message: str):
    return asyncio.run(
        st.session_state.runner.run_debug(
            message,
            user_id=st.session_state.user_id,
            session_id=st.session_state.agroscan_session.id,
            quiet=True
        )
    )


# ============================================================
# PAGE HEADER
# ============================================================

st.title("🐔 AgroScan AI Farm Manager")
st.caption("Your intelligent poultry farm management assistant")

if st.session_state.get("import_summary"):
    st.info(st.session_state.import_summary)


# ============================================================
# SIDEBAR — DEBUG: VIEW CURRENT FARM RECORDS
# ============================================================

with st.sidebar:
    st.subheader("🔍 Debug: View Farm Records")
    if st.button("Load current records"):
        connection = sqlite3.connect(DATABASE_NAME)
        records_df = pd.read_sql_query(
            "SELECT * FROM farm_records ORDER BY record_date", connection
        )
        connection.close()
        st.dataframe(records_df, use_container_width=True)


# ============================================================
# RENDER EXISTING CHAT HISTORY
# ============================================================

for role, text in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(text)


# ============================================================
# HANDLE NEW MESSAGE
# ============================================================

user_message = st.chat_input("Talk to AgroScan about your farm...")

if user_message:

    st.session_state.chat_history.append(("user", user_message))
    with st.chat_message("user"):
        st.markdown(user_message)

    with st.chat_message("assistant"):
        with st.spinner("AgroScan is thinking..."):
            try:
                events = run_agent_turn(user_message)
                final_event = events[-1]

                if final_event.content and final_event.content.parts:
                    response = " ".join(
                        part.text
                        for part in final_event.content.parts
                        if part.text
                    )
                else:
                    response = "No response was generated."

            except Exception as e:
                response = (
                    "I ran into an issue processing that. "
                    "Could you try rephrasing, or ask again?"
                )
                st.session_state.setdefault("last_error", str(e))

            st.markdown(response)

    st.session_state.chat_history.append(("assistant", response))
