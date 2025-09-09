# agent.py
import asyncio
import os

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv
from agents.EdgeCaseAgent.prompt.prompt_factory import PromptFactory

load_dotenv()


AGENT_NAME="EdgeCaseAgent"

class EdgeCaseAgent:
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
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
            output_key="edge_cases"
        )

    async def run_agent(self):
        USER_ID = "user1"
        SESSION_ID = "session1"

        agent = EdgeCaseAgent().get_agent()
        session_service = InMemorySessionService()
        # ensure create_session is awaited (common pitfall)
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

            last_final_text = None

            try:
                # IMPORTANT: iterate all events and keep the last matching final response.
                async for ev in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
                    # OPTIONALLY: debug print for event types (comment out in production)
                    # print(f"[DEBUG] event: id={ev.id} author={ev.author} final={ev.is_final_response()}")

                    # Only consider final responses coming from THIS agent
                    if ev.is_final_response() and getattr(ev, "author",
                                                          None) == AGENT_NAME and ev.content and ev.content.parts:
                        # join all parts to form a single text block
                        parts_text = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                        if parts_text:
                            last_final_text = "".join(parts_text)
                # when the async generator completes, print the last final response we captured (if any)
                if last_final_text:
                    print(last_final_text)
                else:
                    # fallback: no matching final response found
                    print("(no final response produced by the agent)")
            except Exception as e:
                # handle unexpected runtime errors gracefully
                print(f"Error while running agent: {e}")

            print("=" * 20)

if __name__ == "__main__":
    asyncio.run(EdgeCaseAgent().run_agent())
