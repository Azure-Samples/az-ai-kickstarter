import asyncio
import os

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from rich.console import Console
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentThread,
)

load_dotenv()
console = Console()


client = AzureAIAgent.create_client(
    credential=DefaultAzureCredential(),
    endpoint=os.environ["AI_FOUNDRY_PROJECT_CONNECTION_STRING"],
)

os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true" # False by default

from opentelemetry import trace
from azure.monitor.opentelemetry import configure_azure_monitor
application_insights_connection_string = os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
configure_azure_monitor(connection_string=application_insights_connection_string)



async def run(client):
    agents = {agent.name: agent async for agent in client.agents.list_agents()}

    agent_definition = await client.agents.get_agent(agent_id=agents["Moneta_Banking"].id)
    agent = AzureAIAgent(
        client=client,
        definition=agent_definition,
        # plugins=[MenuPlugin()],  # add the sample plugin to the agent
    )
    thread: AzureAIAgentThread = AzureAIAgentThread(client=client)

    try:
        for user_input in ["Hello!", "What's your name?"]:
            response = await agent.get_response(messages=user_input, thread=thread)
            console.print(f"[bold cyan]{response}[/]")
            thread = response.thread
    finally:
        await thread.delete() if thread else None


asyncio.run(run(client))