"""
Chainlit frontend application for our multiagentic application.
"""

import logging
from utils import load_dotenv_from_azd, setup_telemetry
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentThread,
)
from azure.ai.projects.aio import AIProjectClient

import chainlit as cl

load_dotenv_from_azd()
tracer = setup_telemetry(__name__)
logger = logging.getLogger(__name__)

credential = DefaultAzureCredential()

@cl.set_chat_profiles
async def chat_profile():
    logger.info("---------------- Loading chat profiles...")
    async with AzureAIAgent.create_client(credential=credential) as client:
        return [
            cl.ChatProfile(
                name=agent.name,
                markdown_description=agent.description if agent.description  else "No description available.",
            )
            async for agent in client.agents.list_agents()
        ]


@cl.on_chat_start
async def on_chat_start():
    logger.info("---------------- Starting chat session...")
    client : AIProjectClient = AzureAIAgent.create_client(credential=credential)
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
    logger.info(f"---------------- Received message: {message.content}...")

    client : AIProjectClient = cl.user_session.get("client")
    agent_definition = cl.user_session.get("agent")

    if not client or not agent_definition:
        await cl.Message(
            content="No agent selected or client not initialized. Please start a chat session.",
        ).send()
        return
    with tracer.start_as_current_span("chatbot"):
        agent = AzureAIAgent(client=client, definition=agent_definition)
        thread: AzureAIAgentThread = cl.user_session.get("thread", None)

        response = await agent.get_response(messages=message.content, thread=thread)
        thread = response.thread
        cl.user_session.set("thread", thread)

        await cl.Message(content=response.content.content).send()

