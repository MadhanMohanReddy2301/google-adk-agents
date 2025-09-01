import sys
import asyncio
import logging
from typing import AsyncGenerator

from google.adk.agents import LoopAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Import your agents
from agents.sample_agent.agent import SampleAgent
from agents.validation_agent.agent import ValidationAgent

# ---------------------------
# Logging configuration
# ---------------------------
logger = logging.getLogger("LoopOrchestration")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

logging.getLogger("google_adk").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)

# ---------------------------
# Stop condition agent
# ---------------------------
class StopWhenDone(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        stop = False
        if ctx.user_content and ctx.user_content.parts:
            text = "".join([p.text for p in ctx.user_content.parts if p.text]).strip().lower()
            if text == "done":
                stop = True
        logger.debug(f"[StopWhenDone] escalate stop={stop}")
        yield Event(author=self.name, actions=EventActions(escalate=stop))

# ---------------------------
# Wrap agent for labeled output
# ---------------------------
def wrap_agent(agent, label: str):
    class NamedAgent(agent.__class__):
        async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
            async for ev in super()._run_async_impl(ctx):
                if ev.content and ev.content.parts:
                    for p in ev.content.parts:
                        if getattr(p, "text", None):
                            print(f"\n[{label}] {p.text}")
                yield ev
    return NamedAgent(**agent.model_dump())

# ---------------------------
# Build LoopAgent
# ---------------------------
def get_loop_agent():
    sample = SampleAgent().get_agent()
    validation = ValidationAgent().get_agent()

    return LoopAgent(
        name="loop_orchestrator",
        sub_agents=[
            wrap_agent(sample, "SampleAgent"),
            wrap_agent(validation, "ValidationAgent"),
            StopWhenDone(name="StopWhenDone"),
        ],
        max_iterations=5,
    )

# ---------------------------
# Runner and interactive loop
# ---------------------------
async def run_loop_orchestration():
    logger.info("Launching Loop Orchestration...")

    root_agent = get_loop_agent()
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="loop_app", user_id="user1", session_id="session1"
    )

    runner = Runner(agent=root_agent, app_name="loop_app", session_service=session_service)
    logger.info("Type your queries. Type 'done' to exit loop, empty to quit.")

    while True:
        user_input = await asyncio.to_thread(input, "User > ")
        if not user_input.strip():
            logger.info("Exiting orchestration.")
            break

        content = types.Content(role="user", parts=[types.Part(text=user_input)])
        events = runner.run(user_id="user1", session_id="session1", new_message=content)

        for _ in events:
            pass

        print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(run_loop_orchestration())
