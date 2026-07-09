"""
agent.py

Assembles the Skills and Tools into the final Agent, and builds
the Runner/session infrastructure needed to run it.

Deliberately framework-agnostic: does NOT import streamlit or
touch st.secrets directly. app.py reads the Groq API key from
st.secrets and passes it in as a plain string argument, so this
file could in principle be tested or reused outside Streamlit.
"""

import os
import uuid
from datetime import date

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from .skills import farm_manager_core_skill, farm_record_skill
from .tools import (
    farm_record_tool,
    farm_record_lookup_tool,
    most_recent_record_tool,
    farm_summary_tool,
)
from .knowledge_base import search_farm_knowledge_base

farm_knowledge_tool = FunctionTool(search_farm_knowledge_base)


def build_farm_manager_agent():
    """
    Builds the AgroScan Farm Manager Agent: one combined
    SkillToolset (both skills together — never split across
    multiple SkillToolset instances, per the tool-name collision
    lesson) plus all four tools registered directly on the Agent
    (always available from the first turn, no ordering fragility).
    """

    agroscan_toolset = SkillToolset(
        skills=[
            farm_manager_core_skill,
            farm_record_skill,
        ],
        additional_tools=[]
    )

    today_str = date.today().isoformat()

    farm_manager_agent = Agent(

        model=LiteLlm(
            model="groq/meta-llama/llama-4-scout-17b-16e-instruct"
        ),

        name="farm_manager",

        description=(
            "An intelligent poultry farm management system "
            "that assists farmers using specialized capabilities."
        ),

        instruction=f"""
You are AgroScan AI Farm Manager.

You are the single point of interaction for the farmer.

Today's date is {today_str}. Use this to resolve any relative date
or period the farmer mentions (e.g. "yesterday", "this month", "last
week", "three days ago") into exact YYYY-MM-DD date(s) BEFORE calling
any tool. Tools only accept exact dates — never pass a relative term
directly to a tool.

Your responsibility is to help manage poultry farms by
using the available Skills and Tools behind the scenes.

GENERAL RULES

• Never expose internal implementation details.

• Never mention Skills.

• Never mention Tool calls.

• Never mention FunctionTools.

• Never invent farm records.

• Never invent production figures.

• Never invent revenue.

• Treat the Farm Record Book as the single source of truth.

• To record or update daily farm data, call the
record_daily_farm_data tool directly. This tool is
always available.

• To look up a specific date's record, call get_farm_record
directly with an exact date. This tool is always available.

• To find the most recent record on file (when the farmer doesn't
name a specific date), call get_most_recent_farm_record directly.
This tool is always available.

• To summarize performance over a period (totals, profit/loss),
call get_farm_summary directly with an exact start and end date.
This tool is always available.

• For any general layer-poultry farming knowledge question
(housing, feeding, egg handling, biosecurity, flock lifecycle,
record-keeping practices, general health awareness), call
search_farm_knowledge_base directly and answer using ONLY what
it returns. This tool is always available.

• All monetary values must be reported using the ₦ (Naira) symbol,
never $ or any other currency symbol.

• Load the farm-record-management skill to guide how you
interpret and communicate about farm records, lookups, and
summaries.

• Load the farm-manager-core skill to guide your identity,
tone, communication style, and knowledge boundary.

• Never simulate tool execution.

• Wait for tool results before responding.

• If required information is missing,
ask only for the missing information.

Maintain a friendly, professional and practical tone.
""",

        tools=[
            farm_record_tool,
            farm_record_lookup_tool,
            most_recent_record_tool,
            farm_summary_tool,
            farm_knowledge_tool,
            agroscan_toolset,
        ]
    )

    return farm_manager_agent


def build_agent_system(groq_api_key: str):
    """
    Full one-time setup: loads the Groq key, builds the Agent,
    and builds a fresh Runner + session bound to a unique
    user_id/session_id pair (so simultaneous visitors to the
    deployed app don't collide with each other).

    Returns a dict with everything app.py needs to store in
    st.session_state:
        {
            "runner": Runner,
            "session_service": InMemorySessionService,
            "session": Session,
            "user_id": str,
        }
    """

    os.environ["GROQ_API_KEY"] = groq_api_key

    farm_manager_agent = build_farm_manager_agent()

    session_service = InMemorySessionService()

    unique_user_id = str(uuid.uuid4())

    agroscan_session = session_service.create_session_sync(
        app_name="agroscan_app",
        user_id=unique_user_id
    )

    runner = Runner(
        app_name="agroscan_app",
        agent=farm_manager_agent,
        session_service=session_service
    )

    return {
        "runner": runner,
        "session_service": session_service,
        "session": agroscan_session,
        "user_id": unique_user_id,
    }
