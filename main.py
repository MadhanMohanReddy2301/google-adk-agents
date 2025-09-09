from agents.IngestAgent.agent import IngestAgent
from agents.KbAgent.agent import KbAgent
from agents.TestCaseAgent.agent import TestCaseAgent
from agents.EdgeCaseAgent.agent import EdgeCaseAgent
from agents.ComplianceAgent.agent import ComplianceAgent
import asyncio
from dotenv import load_dotenv

from google.adk.agents import SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

ingest_agent = IngestAgent().get_agent()
kb_agent = KbAgent().get_agent()
test_case_agent = TestCaseAgent().get_agent()
edge_case_agent = EdgeCaseAgent().get_agent()
compliance_agent = ComplianceAgent().get_agent()
load_dotenv()

AGENT_NAME = "SequentialRequirementWorkflow"

def build_workflow_agent():
    """
    Compose a SequentialAgent from the two already-created agents.
    The SequentialAgent runs sub_agents in order, sharing the same invocation/session context.
    """

    workflow = SequentialAgent(
        name=AGENT_NAME,
        description="Run ingestion first, then run compliance lookup using ingestion output.",
        sub_agents=[ingest_agent, kb_agent,test_case_agent,edge_case_agent, compliance_agent],
    )
    return workflow

class SequentialWorkflowRunner:
    def __init__(self, workflow_agent):
        self.workflow = workflow_agent
        self.session_service = InMemorySessionService()
        self.user_id = "user1"
        self.session_id = "session1"
        self.runner = Runner(agent=self.workflow, app_name=AGENT_NAME, session_service=self.session_service)

    async def create_session(self):
        await self.session_service.create_session(
            app_name=AGENT_NAME,
            user_id=self.user_id,
            session_id=self.session_id,
        )

    async def run_loop(self):
        """Read lines from stdin and run the sequential workflow for each input."""
        print(f"Initializing [🤖] : {AGENT_NAME}")
        await self.create_session()
        print("Enter your requirement text (empty to exit):")

        while True:
            # non-blocking input wrapped in asyncio.to_thread
            user_input = await asyncio.to_thread(input, "> ")
            if not user_input.strip():
                print("Goodbye!")
                break

            # Build content exactly as your other agents expect (role user + parts)
            content = types.Content(role="user", parts=[types.Part(text=user_input)])

            final_text = None
            try:
                # run_async yields events; capture the final response event and print it
                async for ev in self.runner.run_async(user_id=self.user_id, session_id=self.session_id, new_message=content):
                    if ev.is_final_response() and ev.content and ev.content.parts:
                        parts_text = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                        final_text = "".join(parts_text)
                        print("-------------------NEXT AGENT IS RUNNING----------------------")

                        # Print the final output returned by the last sub-agent (compliance_agent)
                        print(final_text)
            except Exception as e:
                # Surface errors clearly for debugging
                print(f"Error while running sequential workflow: {e}")

            print("=" * 20)


if __name__ == "__main__":
    # Build workflow from your existing agents and run it
    try:
        workflow_agent = build_workflow_agent()
    except Exception as ex:
        print("Failed to build workflow agent:", ex)
        raise

    runner = SequentialWorkflowRunner(workflow_agent)
    asyncio.run(runner.run_loop())
