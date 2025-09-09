# agent.py
import asyncio
import os
import json
from typing import Optional

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

# your existing prompt factory
from agents.TraceabilityAgent.prompt.prompt_factory import PromptFactory

# import existing tools
from agent_tools.bigquery_tool import run_query, fetch_table_rows  # read helpers
from agent_tools import traceability_tool  # writer + emit_audit_entry

load_dotenv()

AGENT_NAME = "TraceabilityAgent"

# --- Tool wrappers (simple JSON-friendly signatures + docstrings) ---
def fetch_existing_rows_for_req(req_id: str, project: Optional[str] = None, max_results: int = 500) -> str:
    """
    fetch_existing_rows_for_req(req_id: str, project: Optional[str]=None, max_results: int=500) -> str
    Return a JSON string containing a list of existing traceability rows for the given req_id.
    Uses bigquery_tool.run_query(...) internally.
    """
    sql = f"""
    SELECT test_case_id, compliance_status, notes
    FROM `{traceability_tool.BQ_TABLE_REF}`
    WHERE req_id = '{req_id}'
    LIMIT {max_results}
    """
    rows = run_query(sql, project=project or traceability_tool.BQ_PROJECT, max_results=max_results)
    return json.dumps(rows, ensure_ascii=False)

def push_traceability_rows(requirement_json: str, test_cases_json: str, created_by: str = "TraceabilityAgent") -> str:
    """
    push_traceability_rows(requirement_json: str, test_cases_json: str, created_by: str="TraceabilityAgent") -> str
    requirement_json: JSON string for requirement object
    test_cases_json: JSON string for list of test-case objects
    Calls traceability_tool.push_traceability(...) and returns its result as JSON string.
    """
    try:
        requirement = json.loads(requirement_json)
        test_cases = json.loads(test_cases_json)
    except Exception as e:
        return json.dumps({"error": f"Invalid JSON input to push_traceability_rows: {e}"}, ensure_ascii=False)

    res = traceability_tool.push_traceability(requirement, test_cases, created_by=created_by)
    return json.dumps(res, ensure_ascii=False)

def sample_query(sql: str, project: Optional[str] = None, max_results: int = 50) -> str:
    """
    sample_query(sql: str, project: Optional[str]=None, max_results: int=50) -> str
    Run a read-only SQL query and return results as JSON string. Useful for ad-hoc checks.
    """
    rows = run_query(sql, project=project, max_results=max_results)
    return json.dumps(rows, ensure_ascii=False)


class TraceabilityAgent:
    @staticmethod
    def get_agent():
        """Create and return an ADK Agent ready to use."""
        print(f"Initializing [🤖] : {AGENT_NAME}")
        agent_prompt = PromptFactory().get_agent_prompt()

        # Pass the wrapper functions into tools; ADK will auto-wrap them as FunctionTools.
        return Agent(
            name=AGENT_NAME,
            model=os.getenv("GEMINI_MODEL"),
            description="TraceabilityAgent (verifies/inserts requirement↔testcase links in BigQuery).",
            instruction=agent_prompt,
            output_key="test_cases",
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
            tools=[
                fetch_existing_rows_for_req,
                push_traceability_rows,
                sample_query,
            ],
        )

    async def run_agent(self):
        USER_ID = "user1"
        SESSION_ID = "session1"

        agent = TraceabilityAgent().get_agent()
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=AGENT_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )

        runner = Runner(agent=agent, app_name=AGENT_NAME, session_service=session_service)

        print("Enter your payload JSON (empty to exit):")
        while True:
            user_input = await asyncio.to_thread(input, "> ")
            if not user_input.strip():
                print("Goodbye!")
                break

            # wrap user input in Content
            content = types.Content(role="user", parts=[types.Part(text=user_input)])

            last_final_text = None
            try:
                # collect the last final response produced by this agent
                async for ev in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
                    if ev.is_final_response() and getattr(ev, "author", None) == AGENT_NAME and ev.content and ev.content.parts:
                        parts_text = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                        if parts_text:
                            last_final_text = "".join(parts_text)
                if last_final_text:
                    print(last_final_text)
                else:
                    print("(no final response produced by the agent)")
            except Exception as e:
                print(f"Error while running agent: {e}")

            print("=" * 20)


if __name__ == "__main__":
    asyncio.run(TraceabilityAgent().run_agent())
