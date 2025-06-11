import asyncio
import json

import pytest
from patterns.debate import DebateOrchestrator
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from utils.util import (
    load_dotenv_from_azd,
)

# Initialize environment and logging
load_dotenv_from_azd()


@pytest.fixture()
def orchestrator():
    return DebateOrchestrator()


def test_debate(orchestrator):
    conversation_messages = [
        {
            "role": "user",
            "name": "user",
            "content": "Blog post about Lord of the Rings",
        }
    ]
    response_chunks = []

    async def collect_chunks():
        async for chunk in orchestrator.process_conversation(
            "test_user", conversation_messages
        ):
            response_chunks.append(chunk)

    asyncio.run(collect_chunks())
    assert len(response_chunks) > 0

    group = Group()
    for chunk in response_chunks:
        group.renderables.append(Text(chunk))
        group.renderables.append(Rule())

    panel = Panel(group, title="Response chunks")

    console = Console()
    console.print(panel)
    console.print(
        Panel(
            Markdown(json.loads(response_chunks[-1])["content"]), title="Final response"
        )
    )
