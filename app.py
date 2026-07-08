import streamlit as st
import sqlite3
import pandas as pd
import asyncio
from datetime import date

from agroscan.database import (
    DATABASE_NAME,
    EXCEL_FILE,
    create_farm_records_table,
    initialize_farm_record_book,
    get_record_count,
)
from agroscan.agent import build_agent_system
from agroscan.service import FarmRecordService


# ============================================================
# PAGE CONFIG — must be the first Streamlit command in the script
# ============================================================
st.set_page_config(
    page_title="AgroScan — Farm Record Book",
    page_icon="🌾",
    layout="centered"
)


# ============================================================
# DESIGN SYSTEM
# Palette: deep forest green (primary), harvest gold (accent),
# muted barn red (sparing emphasis), warm sage-cream (background),
# eggshell (cards), moss charcoal (text).
# Type: Fraunces (display), Karla (body/UI), JetBrains Mono
# (farm data — numbers, dates, records — a deliberate signature
# tying precise figures to the "record book" concept).
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Karla:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Karla', sans-serif;
    color: #26301F;
}

/* ---------- Header ---------- */
.agroscan-header {
    text-align: center;
    padding: 0.5rem 0 1rem 0;
}
.agroscan-header h1 {
    font-family: 'Fraunces', serif;
    font-weight: 700;
    font-size: 2.4rem;
    color: #2F4A34;
    margin-bottom: 0.1rem;
    letter-spacing: -0.01em;
}
.agroscan-header p {
    font-family: 'Karla', sans-serif;
    color: #5C6650;
    font-size: 1rem;
    margin-top: 0;
}
.agroscan-divider {
    height: 3px;
    width: 100%;
    background: linear-gradient(90deg, #C98A2B 0%, #2F4A34 100%);
    border-radius: 3px;
    margin: 0.3rem 0 1.4rem 0;
    opacity: 0.85;
}

/* ---------- Chat bubbles ---------- */
[data-testid="stChatMessage"] {
    border-radius: 14px;
    padding: 0.3rem 0.2rem;
}
div[data-testid="stChatMessageContent"] {
    font-family: 'Karla', sans-serif;
    font-size: 0.98rem;
    line-height: 1.55;
}

/* User bubble */
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
    background-color: #2F4A34;
}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) * {
    color: #FCFAF3 !important;
}

/* Assistant bubble */
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
    background-color: #FCFAF3;
    border-left: 3px solid #C98A2B;
}

/* ---------- Buttons ---------- */
.stButton > button {
    font-family: 'Karla', sans-serif;
    font-weight: 600;
    background-color: #2F4A34;
    color: #FCFAF3;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    transition: background-color 0.15s ease;
}
.stButton > button:hover {
    background-color: #C98A2B;
    color: #26301F;
}
.stButton > button:focus-visible {
    outline: 3px solid #8C3B2E;
    outline-offset: 2px;
}

/* ---------- Chat input ---------- */
[data-testid="stChatInput"] textarea {
    font-family: 'Karla', sans-serif;
    border-radius: 12px !important;
    border: 1.5px solid #C9C3A8 !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #C98A2B !important;
    outline: none;
}

/* ---------- Info banner (import summary) ---------- */
div[data-testid="stAlertContainer"] {
    font-family: 'Karla', sans-serif;
    border-radius: 8px;
    border-left: 4px solid #2F4A34;
}

/* ---------- Sidebar: ledger paper texture ---------- */
section[data-testid="stSidebar"] {
    background-color: #EAE6D6;
    background-image: repeating-linear-gradient(
        180deg,
        transparent,
        transparent 27px,
        rgba(47, 74, 52, 0.10) 28px
    );
}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    font-family: 'Fraunces', serif;
    color: #2F4A34;
}

/* Numbers in metrics and tables — the "precise record" signature */
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
    color: #2F4A34;
    font-weight: 600;
}
[data-testid="stMetricLabel"] {
    font-family: 'Karla', sans-serif;
    color: #5C6650;
}
.stDataFrame, .stDataFrame * {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
}

/* ---------- Sidebar footer ---------- */
.agroscan-sidebar-footer {
    font-family: 'Karla', sans-serif;
    font-size: 0.75rem;
    color: #8C8468;
    text-align: center;
    margin-top: 1.5rem;
    padding-top: 0.8rem;
    border-top: 1px dashed #C9C3A8;
}
</style>
""", unsafe_allow_html=True)


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

st.markdown("""
<div class="agroscan-header">
    <h1>🌾 AgroScan</h1>
    <p>Your Farm's Record Book — Poultry Management, Made Conversational</p>
</div>
<div class="agroscan-divider"></div>
""", unsafe_allow_html=True)

if st.session_state.get("import_summary"):
    st.info(f"📖 {st.session_state.import_summary}")


# ============================================================
# SIDEBAR
# ============================================================

_sidebar_service = FarmRecordService(DATABASE_NAME)

with st.sidebar:

    st.markdown("## 🌾 AgroScan")
    st.caption("Farm Record Book — at a glance")

    st.markdown("### Farm at a Glance")

    total_records = _sidebar_service.get_total_records()
    most_recent = _sidebar_service.get_most_recent_record()
    today_str = date.today().isoformat()
    month_start = today_str[:8] + "01"
    month_summary = _sidebar_service.get_summary(month_start, today_str)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Records", total_records)
    with col2:
        st.metric(
            "Last Entry",
            most_recent["record_date"] if most_recent else "—"
        )

    st.metric(
        "This Month's Net Profit",
        f"₦{month_summary['net_profit']:,.0f}"
        if month_summary["days_recorded"] > 0 else "No data yet"
    )

    st.markdown("---")

    st.markdown("### 📋 View Records")
    if st.button("Load current records", use_container_width=True):
        connection = sqlite3.connect(DATABASE_NAME)
        records_df = pd.read_sql_query(
            "SELECT * FROM farm_records ORDER BY record_date", connection
        )
        connection.close()
        st.dataframe(records_df, use_container_width=True, height=280)

    st.markdown("---")

    with st.expander("💬 What can I ask AgroScan?"):
        st.markdown("""
- *"I collected 28 crates today, used 120kg feed, bird count is 1000, expenses were 60000"*
- *"Actually my expenses today were 62000"*
- *"What was my record for June 15th?"*
- *"What's my most recent record?"*
- *"How did I do this month?"*
- *"Give me a summary from June 1st to June 30th"*
        """)

    st.markdown(
        '<div class="agroscan-sidebar-footer">AgroScan AI Farm Manager<br>Built by Ayoola Tobi</div>',
        unsafe_allow_html=True
    )


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
        with st.spinner("AgroScan is checking the record book..."):
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
