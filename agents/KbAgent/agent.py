# agent.py
import asyncio
import os

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.tools import google_search
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

from agents.KbAgent.prompt.prompt_factory import PromptFactory

load_dotenv()

AGENT_NAME = "KbAgent"

class KbAgent:
    @staticmethod
    def get_agent():
        """Create and return an ADK Agent ready to use."""
        print(f"Initializing [🤖] : {AGENT_NAME}")
        agent_prompt = PromptFactory().get_agent_prompt()

        return Agent(
            name=AGENT_NAME,
            model=os.getenv("GEMINI_MODEL"),
            description="Assistant that uses Google Search to answer questions.",
            instruction=agent_prompt,
            tools=[google_search],
            output_key="health_care_regulations"
        )

    async def run_agent(self):
        USER_ID = "user1"
        SESSION_ID = "session1"

        agent = KbAgent().get_agent()
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=AGENT_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )

        runner = Runner(agent=agent, app_name=AGENT_NAME, session_service=session_service)

        print("Enter your query (empty to exit):")
        while True:
            # get input without blocking the event loop
            user_input = await asyncio.to_thread(input, "> ")
            if not user_input.strip():
                print("Goodbye!")
                break

            content = types.Content(role="user", parts=[types.Part(text=user_input)])

            final_text = None
            try:
                # iterate asynchronously over events; exit when we get the final response
                async for ev in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
                    # is_final_response() marks the concluding message for the turn.
                    if ev.is_final_response() and ev.content and ev.content.parts:
                        # join all parts' text into a single string
                        parts_text = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                        final_text = "".join(parts_text)
                        print(final_text)
                        break
            except Exception as e:
                # handle unexpected runtime errors gracefully
                print(f"Error while running agent: {e}")

            print("=" * 20)

if __name__ == "__main__":
    asyncio.run(KbAgent().run_agent())
