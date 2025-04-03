"""
FastAPI backend application for blog post generation using AI debate orchestration.

This module initializes a FastAPI application that exposes endpoints for generating
blog posts using a debate pattern orchestrator, with appropriate logging, tracing,
and metrics configurations.
"""
import logging
import os

import uvicorn
from fastapi import FastAPI, Body
from fastapi.responses import StreamingResponse
from semantic_kernel.connectors.ai.azure_ai_inference import AzureAIInferenceChatCompletion
from semantic_kernel.core_plugins.time_plugin import TimePlugin
from semantic_kernel.kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.functions import KernelPlugin
from azure.ai.inference.aio import ChatCompletionsClient
from azure.identity.aio import DefaultAzureCredential
from patterns.debate import DebatePattern, DebateSettings, DebatePrompts, DebateConfig
from utils.util import load_dotenv_from_azd, set_up_tracing, set_up_metrics, set_up_logging, create_agent_from_yaml

# Set up basic logging configuration first
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:   %(name)s   %(message)s',
)
logger = logging.getLogger(__name__)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.monitor.opentelemetry.exporter.export').setLevel(logging.WARNING)

# Load environment and setup telemetry after basic logging is configured
load_dotenv_from_azd()
set_up_tracing()
set_up_metrics()
set_up_logging()


# Verify logging is working
logger.info("Starting application")
logger.info("Diagnostics: %s", os.getenv('SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS'))

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
# Check for required environment variables
if not ENDPOINT:
    logger.error("AZURE_OPENAI_ENDPOINT environment variable is not set")
if not API_VERSION:
    logger.error("AZURE_OPENAI_API_VERSION environment variable is not set")

credential = DefaultAzureCredential()

# Define service configurations
SERVICE_CONFIGS = [
    {
        "service_id": "executor",
        "deployment_name": os.getenv("EXECUTOR_AZURE_OPENAI_DEPLOYMENT_NAME")
    },
    {
        "service_id": "utility",
        "deployment_name": os.getenv("UTILITY_AZURE_OPENAI_DEPLOYMENT_NAME")
    }
]

app = FastAPI()


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

# Speaker selection prompt template
speaker_selection_prompt = fr"""
You are the next speaker selector.

- You MUST return ONLY agent name from the list of available agents below.
- You MUST return the agent name and nothing else.
- The agent names are case-sensitive and should not be abbreviated or changed.
- Check the history, and decide WHAT agent is the best next speaker
- You MUST call CRITIC agent to evaluate WRITER RESPONSE
- Critic should never be the first speaker, or speak 2 times in a row.
- YOU MUST OBSERVE AGENT USAGE INSTRUCTIONS.

# AVAILABLE AGENTS
{{{{$agents}}}}

# CHAT HISTORY

{{{{$history}}}}
"""

# Next action prompt template
next_action_prompt = fr"""
Provided the following chat history, what is next action in the agentic chat? 

Provide three word summary.
Always indicate WHO takes the action, for example: WRITER: Writer revises draft
OBS! CRITIC cannot take action, only to evaluate the text and provide a score.

IF the last entry is from CRITIC and the score is above 8 - you MUST respond with "CRITIC: Approves the text."

AGENTS:
- WRITER: Writes and revises the text
- CRITIC: Evaluates the text and provides scoring from 1 to 10

AGENT_CHAT: {{{{ $history }}}}
"""

# Termination function prompt
termination_prompt = fr"""
You are a data extraction assistant.
Check the provided evaluation and return the evalutation score.
It MUST be a single number only, for example - for 6/10 return 6.
{{{{ $evaluation }}}}
"""

# Define settings for different functions
settings = DebateSettings(
    selection=settings_executor,
    next_action=settings_utility,
    termination=settings_utility
)

# Define prompts
prompts = DebatePrompts(
    speaker_selection=speaker_selection_prompt,
    next_action=next_action_prompt,
    termination_function=termination_prompt
)

# Create config
config = DebateConfig(
    kernel=kernel,
    agents=agents,
    settings=settings,
    prompts=prompts,
    # Inline the result extractor function
    result_extractor=lambda messages: [r.to_dict() for r in messages if r.name == "Writer"][-1],
    maximum_iterations=6,
    termination_agents=[critic]
)
    
debate = DebatePattern(config=config)



@app.post("/blog")
async def http_blog(request_body: dict = Body(...)):
    """
    Generate a blog post about a specified topic using the debate orchestrator.
    
    Args:
        request_body (dict): JSON body containing 'topic' and 'user_id' fields.
            - topic (str): The subject for the blog post. Defaults to 'Starwars'.
            - user_id (str): Identifier for the user making the request. Defaults to 'default_user'.
    
    Returns:
        StreamingResponse: A streaming response.
        Chunk can be either a string or contain JSON.
        If the chunk is a string it is a status update. 
        JSON will contain the generated blog post content.
    """
    logger.info('API request received with body %s', request_body)

    topic = request_body.get('topic', 'Starwars')
    user_id = request_body.get('user_id', 'default_user')
    content = f"Write a blog post about {topic}."

    conversation_messages = [{'role': 'user', 'name': 'user', 'content': content}]

    async def doit():
        """
        Asynchronous generator that streams debate orchestrator responses.
        
        Yields:
            str: Chunks of the generated blog post content with newline characters appended.
        """
        async for i in debate.run_debate(user_id, conversation_messages):
            yield i + '\n'

    return StreamingResponse(doit(), media_type="application/json")



if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)