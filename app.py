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
# DESIGN SYSTEM — "Harvest Dawn" Theme
# A warm, inviting agricultural design with:
# - Sunrise-inspired gradient palette (warm golds, deep greens)
# - Modern, clean typography with agricultural personality
# - Card-based layout for data presentation
# - Subtle nature-inspired textures and patterns
# - Professional yet approachable farm management feel
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ---------- Global Reset & Base ---------- */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
    color: #2D2D2D;
    background: linear-gradient(135deg, #FEF9F0 0%, #F5EDDF 100%);
}

/* ---------- Main Container ---------- */
.main {
    background: transparent;
}

/* ---------- Header with Sunrise Gradient ---------- */
.harvest-header {
    background: linear-gradient(135deg, #2D5A27 0%, #4A7C3F 50%, #C49A3C 100%);
    padding: 2rem 2.5rem;
    border-radius: 20px;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(45, 90, 39, 0.25);
}

.harvest-header::before {
    content: "🌾";
    position: absolute;
    right: -10px;
    top: -30px;
    font-size: 140px;
    opacity: 0.08;
    transform: rotate(-15deg);
}

.harvest-header::after {
    content: "☀️";
    position: absolute;
    right: 60px;
    bottom: -20px;
    font-size: 80px;
    opacity: 0.06;
}

.harvest-header h1 {
    font-family: 'Playfair Display', serif;
    font-weight: 700;
    color: #FFFFFF;
    font-size: 2.8rem;
    margin: 0;
    text-shadow: 0 2px 12px rgba(0,0,0,0.15);
    letter-spacing: -0.5px;
}

.harvest-header .subtitle {
    font-family: 'Inter', sans-serif;
    font-weight: 400;
    color: rgba(255,255,255,0.92);
    font-size: 1.1rem;
    margin: 0.2rem 0 0.5rem 0;
    opacity: 0.9;
}

.harvest-header .badge-container {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-top: 0.5rem;
}

.harvest-header .badge {
    display: inline-block;
    background: rgba(255,255,255,0.18);
    backdrop-filter: blur(10px);
    padding: 4px 16px;
    border-radius: 20px;
    font-size: 0.8rem;
    color: white;
    border: 1px solid rgba(255,255,255,0.1);
    font-weight: 500;
    letter-spacing: 0.3px;
}

/* ---------- Decorative Divider ---------- */
.harvest-divider {
    height: 4px;
    background: linear-gradient(90deg, #C49A3C, #4A7C3F, #2D5A27);
    border-radius: 4px;
    margin: 0.5rem 0 1.8rem 0;
    opacity: 0.6;
}

/* ---------- Chat Bubbles ---------- */
[data-testid="stChatMessage"] {
    border-radius: 16px !important;
    padding: 0.3rem 0.2rem !important;
    margin-bottom: 0.5rem !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
}

div[data-testid="stChatMessageContent"] {
    font-family: 'Inter', sans-serif;
    font-size: 0.98rem;
    line-height: 1.6;
}

/* User bubble - Warm Green */
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
    background: linear-gradient(135deg, #2D5A27 0%, #3D7A35 100%) !important;
    border: none !important;
    border-radius: 16px 16px 4px 16px !important;
}

div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) * {
    color: #FFFFFF !important;
}

/* Assistant bubble - Warm Cream */
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
    background: #FFFFFF !important;
    border-left: 4px solid #C49A3C !important;
    border-radius: 16px 16px 16px 4px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
}

div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) * {
    color: #2D2D2D !important;
}

/* ---------- Buttons ---------- */
.stButton > button {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    background: linear-gradient(135deg, #2D5A27 0%, #4A7C3F 100%);
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 0.6rem 1.2rem;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(45, 90, 39, 0.2);
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(45, 90, 39, 0.3);
    background: linear-gradient(135deg, #3D7A35 0%, #5A9A4F 100%);
}

.stButton > button:active {
    transform: translateY(0px);
}

/* ---------- Chat Input ---------- */
[data-testid="stChatInput"] textarea {
    font-family: 'Inter', sans-serif;
    border-radius: 14px !important;
    border: 2px solid #D4C9B0 !important;
    background: #FFFFFF !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
}

[data-testid="stChatInput"] textarea:focus {
    border-color: #C49A3C !important;
    box-shadow: 0 0 0 4px rgba(196, 154, 60, 0.15) !important;
}

/* ---------- Info/Alerts ---------- */
div[data-testid="stAlertContainer"] {
    border-radius: 12px !important;
    border-left: 4px solid #C49A3C !important;
    background: #FEF9F0 !important;
    font-family: 'Inter', sans-serif;
}

/* ---------- Metrics ---------- */
[data-testid="stMetric"] {
    background: #FFFFFF;
    padding: 0.8rem 1rem;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    border: 1px solid rgba(196, 154, 60, 0.15);
    transition: all 0.3s ease;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}

[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    color: #2D5A27 !important;
    font-weight: 600 !important;
    font-size: 1.8rem !important;
}

[data-testid="stMetricLabel"] {
    font-family: 'Inter', sans-serif !important;
    color: #6B6B6B !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
}

/* ---------- Sidebar - Warm Earth Tone ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F8F4EA 0%, #F0EAD9 100%);
    border-right: 2px solid rgba(196, 154, 60, 0.15);
    padding: 1.5rem 1rem;
}

section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    font-family: 'Playfair Display', serif;
    color: #2D5A27;
}

section[data-testid="stSidebar"] .stCaption {
    color: #7A7A7A;
}

section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stDateInput label {
    color: #4A4A4A !important;
    font-weight: 500;
}

/* ---------- Sidebar Footer ---------- */
.sidebar-footer {
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    color: #8A8A7A;
    text-align: center;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 2px dashed rgba(196, 154, 60, 0.25);
}

/* ---------- Dataframe ---------- */
.stDataFrame {
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid rgba(196, 154, 60, 0.15) !important;
}

.stDataFrame thead tr th {
    background: linear-gradient(135deg, #2D5A27 0%, #4A7C3F 100%) !important;
    color: white !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    padding: 10px !important;
}

.stDataFrame tbody tr {
    transition: all 0.2s ease !important;
}

.stDataFrame tbody tr:hover {
    background: #FEF9F0 !important;
}

.stDataFrame td {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
}

/* ---------- Expander ---------- */
.streamlit-expanderHeader {
    background: #F8F4EA !important;
    border-radius: 10px !important;
    border: 1px solid rgba(196, 154, 60, 0.2) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    color: #2D5A27 !important;
}

.streamlit-expanderContent {
    background: #FFFFFF !important;
    border-radius: 0 0 10px 10px !important;
    border: 1px solid rgba(196, 154, 60, 0.2) !important;
    border-top: none !important;
}

/* ---------- Spinner ---------- */
.stSpinner > div {
    border-color: #4A7C3F !important;
    border-right-color: transparent !important;
}

/* ---------- Scrollbar ---------- */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

::-webkit-scrollbar-track {
    background: #F5EDDF;
    border-radius: 10px;
}

::-webkit-scrollbar-thumb {
    background: #C49A3C;
    border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
    background: #2D5A27;
}

/* ---------- Responsive ---------- */
@media (max-width: 768px) {
    .harvest-header {
        padding: 1.5rem;
    }
    .harvest-header h1 {
        font-size: 2rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
}

/* ---------- Welcome Message ---------- */
.welcome-container {
    text-align: center;
    padding: 2.5rem 1.5rem;
    background: #FFFFFF;
    border-radius: 20px;
    border: 1px solid rgba(196, 154, 60, 0.15);
    box-shadow: 0 4px 20px rgba(0,0,0,0.04);
}

.welcome-container .icon {
    font-size: 3.5rem;
    margin-bottom: 0.5rem;
}

.welcome-container h3 {
    font-family: 'Playfair Display', serif;
    color: #2D5A27;
    font-size: 1.8rem;
    margin: 0.5rem 0;
}

.welcome-container p {
    color: #5A5A5A;
    max-width: 500px;
    margin: 0.5rem auto;
}

.welcome-tags {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    flex-wrap: wrap;
    margin-top: 1.2rem;
}

.welcome-tags span {
    background: #F8F4EA;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.85rem;
    color: #2D5A27;
    font-weight: 500;
    border: 1px solid rgba(196, 154, 60, 0.15);
}

/* ---------- Sidebar Metric Cards ---------- */
.sidebar-metric {
    background: rgba(255,255,255,0.6);
    border-radius: 10px;
    padding: 0.5rem 1rem;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.3);
}

/* ---------- Record Details ---------- */
.record-detail {
    background: #FFFFFF;
    padding: 1rem;
    border-radius: 10px;
    border: 1px solid rgba(196, 154, 60, 0.15);
}

.record-detail p {
    margin: 0.3rem 0;
    font-family: 'Inter', sans-serif;
}

.record-detail strong {
    color: #2D5A27;
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
# PAGE HEADER — Harvest Theme
# ============================================================

st.markdown("""
<div class="harvest-header">
    <h1>🌾 AgroScan</h1>
    <div class="subtitle">Your Farm's Record Book — Poultry Management, Made Conversational</div>
    <div class="badge-container">
        <span class="badge">🚀 AI-Powered</span>
        <span class="badge">📊 Smart Analytics</span>
        <span class="badge">🌿 Sustainable Farming</span>
    </div>
</div>
<div class="harvest-divider"></div>
""", unsafe_allow_html=True)

if st.session_state.get("import_summary"):
    st.info(f"📖 {st.session_state.import_summary}")


# ============================================================
# SIDEBAR — Harvest Dashboard
# ============================================================

_sidebar_service = FarmRecordService(DATABASE_NAME)

with st.sidebar:

    st.markdown("## 🌾 AgroScan")
    st.caption("📋 Farm Record Book — at a glance")
    st.markdown("---")

    st.markdown("### 📊 Farm at a Glance")

    total_records = _sidebar_service.get_total_records()
    most_recent = _sidebar_service.get_most_recent_record()
    today_str = date.today().isoformat()
    month_start = today_str[:8] + "01"
    month_summary = _sidebar_service.get_summary(month_start, today_str)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("📅 Total Records", total_records)
    with col2:
        st.metric(
            "🕒 Last Entry",
            most_recent["record_date"] if most_recent else "—"
        )

    st.metric(
        "💰 Month Net Profit",
        f"₦{month_summary['net_profit']:,.0f}"
        if month_summary["days_recorded"] > 0 else "📭 No data yet"
    )

    st.markdown("---")

    st.markdown("### 📋 View Records")
    if st.button("📊 Load current records", use_container_width=True):
        connection = sqlite3.connect(DATABASE_NAME)
        records_df = pd.read_sql_query(
            "SELECT * FROM farm_records ORDER BY record_date", connection
        )
        connection.close()
        st.dataframe(records_df, use_container_width=True, height=280)

    st.markdown("---")

    with st.expander("💬 What can I ask AgroScan?", expanded=False):
        st.markdown("""
        **📝 Record daily data:**  
        *"I collected 28 crates today, used 120kg feed, bird count is 1000, expenses were 60000"*  
        
        **✏️ Update a record:**  
        *"Actually my expenses today were 62000"*  
        
        **🔍 View specific date:**  
        *"What was my record for June 15th?"*  
        
        **📋 Most recent:**  
        *"What's my most recent record?"*  
        
        **📈 Performance summary:**  
        *"How did I do this month?"*  
        
        **📊 Period report:**  
        *"Give me a summary from June 1st to June 30th"*
        """)

    st.markdown("---")
    
    # Quick stats
    if total_records > 0:
        st.markdown("### 🎯 Quick Stats")
        all_records = _sidebar_service.get_all_records()
        total_crates = sum(r["crates_collected"] for r in all_records)
        avg_crates = total_crates / total_records if total_records > 0 else 0
        total_revenue = sum(r["revenue"] for r in all_records)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🥚 Total Crates", f"{total_crates:,}")
        with col2:
            st.metric("📊 Avg/Day", f"{avg_crates:.1f}")
        
        st.metric("💰 Total Revenue", f"₦{total_revenue:,.2f}")

    st.markdown(
        '<div class="sidebar-footer">🌾 AgroScan AI Farm Manager<br>Built by Ayoola Tobi</div>',
        unsafe_allow_html=True
    )


# ============================================================
# RENDER EXISTING CHAT HISTORY
# ============================================================

if not st.session_state.chat_history:
    # Welcome message with agricultural theme
    st.markdown("""
    <div class="welcome-container">
        <div class="icon">🌾</div>
        <h3>Welcome to AgroScan!</h3>
        <p>Your intelligent poultry farm management assistant. I'm here to help you manage your farm records, track performance, and provide insights.</p>
        <div class="welcome-tags">
            <span>📊 View Records</span>
            <span>📝 Add Daily Data</span>
            <span>📈 Get Summaries</span>
            <span>💰 Check Profit</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

for role, text in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(text)


# ============================================================
# HANDLE NEW MESSAGE
# ============================================================

user_message = st.chat_input("💬 Talk to AgroScan about your farm...")

if user_message:

    st.session_state.chat_history.append(("user", user_message))
    with st.chat_message("user"):
        st.markdown(user_message)

    with st.chat_message("assistant"):
        with st.spinner("🌾 AgroScan is checking the record book..."):
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
