# agent.py
import asyncio
import os

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

from agents.sample_agent.prompt.prompt_factory import PromptFactory

load_dotenv()


AGENT_NAME="sample_agent"

class SampleAgent:
    @staticmethod
    def get_agent() :
        """Create and return an ADK Agent ready to use."""

        print(f"Initializing [🤖] : {AGENT_NAME}")
        agent_prompt = PromptFactory().get_agent_prompt()

        return Agent(
            name=AGENT_NAME,
            model=os.getenv("GEMINI_MODEL"),
            description="Assistant that uses Google Search to answer questions.",
            instruction=agent_prompt,
            tools=[google_search],

        )

    async def run_agent(self):

        APP_NAME = "search_app"
        USER_ID = "user1"
        SESSION_ID = "session1"

        agent = SampleAgent().get_agent()
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID)

        runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

        print("Enter your query (empty to exit):")
        while True:
            user_input = await asyncio.to_thread(input, "> ")
            if not user_input.strip():
                print("Goodbye!")
                break

            content = types.Content(role="user", parts=[types.Part(text=user_input)])
            events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

            for ev in events:
                if ev.content and ev.content.parts:
                    for p in ev.content.parts:
                        print(p.text)
            print("="*20)

if __name__ == "__main__":
    asyncio.run(SampleAgent().run_agent())
