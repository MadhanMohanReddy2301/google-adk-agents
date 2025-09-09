import sys
import asyncio
import logging
from typing import AsyncGenerator

from google.adk.agents import LoopAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from agents.IngestAgent.agent import IngestAgent
from agents.KbAgent.agent import KbAgent

# ─────────────────────────────────
# Logging setup (stdout = white text)
logger = logging.getLogger("LoopOrchestration")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
logger.addHandler(handler)
logging.getLogger("google_adk").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
# ─────────────────────────────────

# --- Exit tool ---
def exit_loop(tool_context: ToolContext):
    """Tool that escalates termination of LoopAgent."""
    print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
    tool_context.actions.escalate = True
    return {}

# --- Wrap output with agent labels (skip non-text parts) ---
def wrap_agent(agent, label: str):
    class NamedAgent(agent.__class__):
        async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
            buffer = []
            async for ev in super()._run_async_impl(ctx):
                if ev.content and ev.content.parts:
                    for p in ev.content.parts:
                        if getattr(p, "text", None):  # skip function_call etc.
                            buffer.append(p.text)
                yield ev
            if buffer:
                print(f"\n[{label}] {' '.join(buffer)}")
    return NamedAgent(
        name=agent.name,
        model=agent.model,
        description=agent.description,
        instruction=agent.instruction,
        tools=agent.tools,
        output_key=agent.output_key,
    )

# --- Build Loop Agent with exit strategy ---
def get_loop_agent():
    sample = IngestAgent().get_agent()
    validation = KbAgent().get_agent()

    # Validation agent updated to call exit_loop when correct
    validation_with_exit = LlmAgent(
        name=validation.name,
        model=validation.model,
        description=validation.description,
        instruction=(
            validation.instruction
            + "\n\nIf the validation is fully correct and no further refinement is needed, "
              "you MUST call the 'exit_loop' tool and output nothing else."
        ),
        tools=[exit_loop],
        output_key="validation_result",
    )

    return LoopAgent(
        name="loop_orchestrator",
        sub_agents=[
            wrap_agent(sample, "SampleAgent"),
            wrap_agent(validation_with_exit, "ValidationAgent"),
        ],
        max_iterations=5,

    )

# --- Runner ---
async def run_loop_orchestration():
    logger.info("Launching Loop Orchestration with exit_loop tool...")
    agent = get_loop_agent()
    ss = InMemorySessionService()
    await ss.create_session(app_name="loop_app", user_id="user1", session_id="session1")
    runner = Runner(agent=agent, app_name="loop_app", session_service=ss)

    logger.info("Type your query. Loop will stop automatically if validation calls exit_loop.")
    while True:
        user_input = await asyncio.to_thread(input, "User > ")
        if not user_input.strip():
            logger.info("Exiting orchestration.")
            break

        content = types.Content(role="user", parts=[types.Part(text=user_input)])
        for _ in runner.run(user_id="user1", session_id="session1", new_message=content):
            pass

        print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(run_loop_orchestration())
