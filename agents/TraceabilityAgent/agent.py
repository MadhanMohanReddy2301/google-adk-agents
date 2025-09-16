# agent.py
import asyncio
import os
import json
from typing import Optional

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
# NEW imports for MCP toolset
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_toolset import SseConnectionParams

from google.genai import types
from dotenv import load_dotenv

# your existing prompt factory
from agents.TraceabilityAgent.prompt.prompt_factory import PromptFactory



load_dotenv()

AGENT_NAME = "TraceabilityAgent"

class TraceabilityAgent:
    @staticmethod
    def get_agent():
        """Create and return an ADK Agent ready to use."""
        print(f"Initializing [🤖] : {AGENT_NAME}")
        agent_prompt = PromptFactory().get_agent_prompt()

        # NEW: initialize MCPToolset for Jira MCP server
        big_query_mcp_url = os.getenv("BIGQUERY_MCP_SERVER_URL")
        mcp_toolset = McpToolset(
            connection_params=SseConnectionParams(url=big_query_mcp_url),

        )
        # Pass the wrapper functions into tools; ADK will auto-wrap them as FunctionTools.
        return Agent(
            name=AGENT_NAME,
            model=os.getenv("GEMINI_MODEL"),
            description="TraceabilityAgent (verifies/inserts requirement↔testcase links in BigQuery).",
            instruction=agent_prompt,
            tools=[mcp_toolset],
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
