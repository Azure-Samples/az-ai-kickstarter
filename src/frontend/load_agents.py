import asyncio
import os
from pathlib import Path

import yaml
from utils import load_dotenv_from_azd
from azure.identity.aio import DefaultAzureCredential
from rich.console import Console
from semantic_kernel.agents import (
    AzureAIAgent,
)

load_dotenv_from_azd()
console = Console()


async def main() -> None:
    """Main function to load agents from YAML files and create/update them in Azure AI."""
    async with (
        DefaultAzureCredential() as creds,
        AzureAIAgent.create_client(credential=creds) as client,
    ):
        agents = {agent.name: agent async for agent in client.agents.list_agents()}

        if os.environ.get("RELOAD") is not None:
            for agent in agents.values():
                console.print(
                    f"Deleting agent: [bold cyan]{agent.name}[/] - [blue]{agent.description}[/]..."
                )
                await client.agents.delete_agent(agent_id=agent.id)
            agents = {}

        for spec in sorted(Path("agents").glob("*.yaml")):
            with open(spec, "r") as f:
                agent_spec = yaml.safe_load(f)
                if "model" not in agent_spec:
                    agent_spec["model"] = os.environ[
                        "AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"
                    ]

            if agent_spec["name"] not in agents:
                console.print(
                    f"Creating agent: [bold cyan]{agent_spec['name']}[/] - [blue]{agent_spec.get('description')}[/]..."
                )
                await client.agents.create_agent(**agent_spec)
            else:
                console.print(
                    f"Agent [bold cyan]{agent_spec['name']}[/] - [blue]{agents[agent_spec['name']].description}[/] already exists, updating..."
                )
                for t in agents[agent_spec["name"]].tools:
                    console.print(f"  - Tool: [bold cyan]{t}[/]")
                await client.agents.update_agent(
                    agent_id=agents[agent_spec["name"]].id, **agent_spec
                )


if __name__ == "__main__":
    asyncio.run(main())
