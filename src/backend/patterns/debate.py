import os
import json
import logging
import datetime
import inspect
from typing import List, Dict, AsyncGenerator

from patterns.score_based_termination_strategy import ScoreBasedTerminationStrategy
from semantic_kernel.kernel import Kernel
from semantic_kernel.agents import AgentGroupChat
from semantic_kernel.agents.strategies import KernelFunctionSelectionStrategy
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings

from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.core_plugins.time_plugin import TimePlugin
from semantic_kernel.functions import KernelPlugin, KernelFunctionFromPrompt

from semantic_kernel.connectors.ai.azure_ai_inference import AzureAIInferenceChatCompletion
from azure.ai.inference.aio import ChatCompletionsClient
from azure.identity.aio import DefaultAzureCredential

from opentelemetry.trace import get_tracer

from utils.util import create_agent_from_yaml, load_dotenv_from_azd

load_dotenv_from_azd()
logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

# Module-level configuration constants from environment variables
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Check for required environment variables
if not ENDPOINT:
    logger.error("AZURE_OPENAI_ENDPOINT environment variable is not set")
if not API_VERSION:
    logger.error("AZURE_OPENAI_API_VERSION environment variable is not set")

# Module-level initialization of credential
credential = DefaultAzureCredential()

# Define service configurations
SERVICE_CONFIGS = [
    {
        "service_id": "executor",
        "deployment_env_var": "EXECUTOR_AZURE_OPENAI_DEPLOYMENT_NAME",
        "deployment_name": os.getenv("EXECUTOR_AZURE_OPENAI_DEPLOYMENT_NAME")
    },
    {
        "service_id": "utility",
        "deployment_env_var": "UTILITY_AZURE_OPENAI_DEPLOYMENT_NAME",
        "deployment_name": os.getenv("UTILITY_AZURE_OPENAI_DEPLOYMENT_NAME")
    }
]

# Log warnings for missing deployment names
for config in SERVICE_CONFIGS:
    if not config["deployment_name"]:
        logger.error(f"{config['deployment_env_var']} environment variable is not set")

# Create services using mapping
services = []
if ENDPOINT and API_VERSION:
    services = [
        AzureAIInferenceChatCompletion(
            ai_model_id=config["service_id"],
            service_id=config["service_id"],
            client=ChatCompletionsClient(
                endpoint=f"{str(ENDPOINT).strip('/')}/openai/deployments/{config['deployment_name']}",
                api_version=API_VERSION,
                credential=credential,
                credential_scopes=["https://cognitiveservices.azure.com/.default"],
            )
        )
        for config in SERVICE_CONFIGS
        if config["deployment_name"]  # Only create if deployment name is available
    ]

settings_executor = AzureChatPromptExecutionSettings(service_id="executor", temperature=0)
settings_utility = AzureChatPromptExecutionSettings(service_id="utility", temperature=0)

kernel = Kernel(
    services=services,
    plugins=[KernelPlugin.from_object(plugin_instance=TimePlugin(), plugin_name="time")]
)

writer = create_agent_from_yaml(
    service_id="executor",
    kernel=kernel,
    definition_file_path="agents/writer.yaml"
)

critic = create_agent_from_yaml(
    service_id="executor",
    kernel=kernel,
    definition_file_path="agents/critic.yaml"
)

agents = [writer, critic]

agents_string = "\n".join([f"{agent.name}: {agent.description}" for agent in agents])
speaker_selection_prompt = inspect.cleandoc(f"""
            You are the next speaker selector.

            - You MUST return ONLY agent name from the list of available agents below.
            - You MUST return the agent name and nothing else.
            - The agent names are case-sensitive and should not be abbreviated or changed.
            - Check the history, and decide WHAT agent is the best next speaker
            - You MUST call CRITIC agent to evaluate WRITER RESPONSE
            - YOU MUST OBSERVE AGENT USAGE INSTRUCTIONS.

            # AVAILABLE AGENTS

            {agents_string}

            # CHAT HISTORY

            {{$history}}
        """)

selection_function = KernelFunctionFromPrompt(
    function_name="SpeakerSelector",
    prompt_execution_settings=settings_executor,
    prompt=speaker_selection_prompt
)

selection_strategy = KernelFunctionSelectionStrategy(
    kernel=kernel,
    function=selection_function,
    result_parser=lambda output: critic.name if output.value is None else output.value[0].content,
    agent_variable_name="agents",
    history_variable_name="history"
)

# Create termination strategy - can be modified during runtime
termination_strategy = ScoreBasedTerminationStrategy(
    kernel=kernel,
    agents=[critic],
    maximum_iterations=6,
    termination_function = KernelFunctionFromPrompt(
        function_name="TerminationEvaluator",
        prompt_execution_settings=settings_utility,
        prompt=inspect.cleandoc("""
                You are a data extraction assistant.
                Check the provided evaluation and return the evalutation score.
                It MUST be a single number only, for example - for 6/10 return 6.
                {{$evaluation}}
            """)
    )
)

# Create agent group chat - can be modified during runtime
agent_group_chat = AgentGroupChat(
    agents=agents,
    selection_strategy=selection_strategy,
    termination_strategy=termination_strategy
)


async def describe_next_action(kernel, settings, messages):
    """
    Determines the next action in an agent conversation workflow.
    
    Args:
        kernel: The Semantic Kernel instance
        settings: Execution settings for the prompt
        messages: Conversation history between agents
        
    Returns:
        str: A three-word summary of the next action, indicating which agent should act
        
    This function analyzes the conversation context to determine workflow progression
    between WRITER and CRITIC agents, with special handling for high-scoring CRITIC responses.
    """
    next_action = await kernel.invoke_prompt(
        function_name="describe_next_action",
        prompt=inspect.cleandoc(f"""
        Provided the following chat history, what is next action in the agentic chat? 
        
        Provide three word summary.
        Always indicate WHO takes the action, for example: WRITER: Writes revises draft
        OBS! CRITIC cannot take action, only to evaluate the text and provide a score.
        
        IF the last entry is from CRITIC and the score is above 8 - you MUST respond with "CRITIC: Approves the text."
        
        AGENTS:
        - WRITER: Writes and revises the text
        - CRITIC: Evaluates the text and provides scroring from 1 to 10
        
        AGENT_CHAT: {messages}
        
        """),
        settings=settings
    )
    return next_action


async def process_conversation(user_id: str, conversation_messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """
    Process a conversation by orchestrating a debate between AI agents.
    
    Args:
        user_id: Unique identifier for the user
        conversation_messages: List of conversation message dictionaries
        
    Yields:
        Status updates and final response
    """
    # Convert conversation history to ChatMessageContent objects
    chat_history = [
        ChatMessageContent(
            role=AuthorRole(msg.get('role')),
            name=msg.get('name'),
            content=msg.get('content')
        )
        for msg in filter(lambda m: m['role'] in ("assistant", "user"), conversation_messages)
    ]

    # Add chat history to the agent group chat
    await agent_group_chat.add_chat_messages(chat_history)

    current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    session_id = f"{user_id}-{current_time}"
    messages = []

    # Run the conversation with tracing
    with tracer.start_as_current_span(session_id):
        yield "WRITER: Prepares the initial draft"
        async for a in agent_group_chat.invoke():
            logger.info(f"Agent: {a.to_dict()}")
            messages.append(a.to_dict())
            next_action = await describe_next_action(kernel, settings_utility, messages)
            logger.info(f"{next_action}")
            yield f"{next_action}"

    # Get final response
    response = list(reversed([item async for item in agent_group_chat.get_chat_messages()]))
    reply = [r for r in response if r.name == "Writer"][-1].to_dict()

    # Return final response as JSON
    yield json.dumps(reply)


# This is the main entry point - more functional API design
async def run_debate(user_id: str, conversation_history: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """Public API: Run a debate for the given conversation history."""
    async for message in process_conversation(user_id, conversation_history):
        yield message
