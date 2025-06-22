"""
Chainlit frontend application for our multiagentic application.
"""

import json
import logging

import chainlit as cl

from azure.identity.aio import DefaultAzureCredential
from rich.console import Console
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentThread,
)
from utils import load_dotenv_from_azd

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(console.file)],
)


def is_valid_json(json_string):
    """
    Validate if a string is properly formatted JSON.

    Args:
        json_string (str): The string to validate as JSON

    Returns:
        bool: True if string is valid JSON, False otherwise
    """
    try:
        json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False


# Initialize environment
load_dotenv_from_azd()


credential = DefaultAzureCredential()


@cl.set_chat_profiles
async def chat_profile():
    logging.info("---------------- Loading chat profiles...")
    async with (
        credential,
        AzureAIAgent.create_client(credential=credential) as client,
    ):
        return [
            cl.ChatProfile(
                name=agent.name,
                markdown_description=agent.description,
            )
            async for agent in client.agents.list_agents()
        ]


@cl.on_chat_start
async def on_chat_start():
    logging.info("---------------- Starting chat session...")
    client = AzureAIAgent.create_client(credential=credential)
    cl.user_session.set("client", client)
    cl.user_session.set(
        "agents", [agent async for agent in client.agents.list_agents()]
    )
    agent_name = cl.user_session.get("chat_profile")
    await cl.Message(
        content=f"Starting chat using the **«{agent_name}»** agent.",
    ).send()
    cl.user_session.set(
        "agent",
        next(
            (
                agent
                for agent in cl.user_session.get("agents")
                if agent["name"] == agent_name
            ),
            None,
        ),
    )


@cl.on_message
async def on_message(message: cl.Message):
    logging.info(f"---------------- Received message: {message.content}...")

    client = cl.user_session.get("client")
    agent_definition = cl.user_session.get("agent")

    if not client or not agent_definition:
        await cl.Message(
            content="No agent selected or client not initialized. Please start a chat session.",
        ).send()
        return

    agent = AzureAIAgent(client=client, definition=agent_definition)
    thread: AzureAIAgentThread = cl.user_session.get("thread", None)

    response = await agent.get_response(messages=message.content, thread=thread)
    thread = response.thread
    cl.user_session.set("thread", thread)

    await cl.Message(content=response.content.content).send()
