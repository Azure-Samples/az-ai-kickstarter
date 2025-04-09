"""
Examples demonstrating how to use the DebatePattern class with different agent configurations.
"""

from typing import List, Dict, AsyncGenerator
import os
from semantic_kernel.kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.functions import KernelPlugin
from semantic_kernel.core_plugins.time_plugin import TimePlugin
from semantic_kernel.connectors.ai.azure_ai_inference import AzureAIInferenceChatCompletion
from azure.ai.inference.aio import ChatCompletionsClient
from azure.identity.aio import DefaultAzureCredential

from patterns.debate import DebatePattern, DebateConfig, DebateSettings, DebatePrompts
from utils.util import create_agent_from_yaml, load_dotenv_from_azd

from src.backend.utils.util import create_chat_model

load_dotenv_from_azd()

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
    
    
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


services = []
if ENDPOINT and API_VERSION:
    services = [
        create_chat_model(
            service_id=config["service_id"],
            deployment_name=config["deployment_name"],
            endpoint=ENDPOINT,
            api_version=API_VERSION
        )
        for config in SERVICE_CONFIGS
        if config["deployment_name"]
    ]

# Set up the kernel with services and plugins
kernel = Kernel(
    services=services,
    plugins=[KernelPlugin.from_object(plugin_instance=TimePlugin(), plugin_name="time")]
)

async def create_brainstorming_debate() -> DebatePattern:
    """
    Example of creating a debate pattern for brainstorming with 3 agents:
    - Creator (generates ideas)
    - Enhancer (improves ideas)
    - Evaluator (assesses the quality of ideas)
    
    Returns:
        A configured DebatePattern instance
    """

    # Create custom agents from YAML
    # These YAML files would need to be created separately
    creator = create_agent_from_yaml(
        service_id="executor",
        kernel=kernel,
        definition_file_path="agents/brainstorming/creator.yaml"  # This would need to be created
    )
    
    enhancer = create_agent_from_yaml(
        service_id="executor",
        kernel=kernel,
        definition_file_path="agents/brainstorming/enhancer.yaml"  # This would need to be created
    )
    
    evaluator = create_agent_from_yaml(
        service_id="executor",
        kernel=kernel,
        definition_file_path="agents/brainstorming/evaluator.yaml"  # This would need to be created
    )
    
    agents = [creator, enhancer, evaluator]
    
    # Define execution settings
    settings_executor = AzureChatPromptExecutionSettings(service_id="executor", temperature=0.7)
    settings_utility = AzureChatPromptExecutionSettings(service_id="utility", temperature=0)
    
    # Custom speaker selection prompt for brainstorming
    speaker_selection_prompt = fr"""
    You are the brainstorming orchestrator.

    - Return ONLY agent name from the list of available agents below.
    - Return the agent name exactly as shown, without any other text.
    - The names are case-sensitive.
    - Based on the history, select the most appropriate next speaker:
      * CREATOR should go first to generate initial ideas
      * ENHANCER should improve on ideas after they are generated
      * EVALUATOR should assess ideas only after they've been enhanced
      * After evaluation, CREATOR should generate new ideas based on feedback
    - Never let the same agent speak twice in a row.

    # AVAILABLE AGENTS

    {{{{$agents}}}}

    # CHAT HISTORY

    {{{{$history}}}}
    """
    
    # Custom next action description
    next_action_prompt = fr"""
    Based on the chat history below, describe the next action in the brainstorming session.
    
    Provide a brief (3-5 word) description of what's happening next.
    Always include the agent name, for example: "CREATOR: Generating new ideas"
    
    If the EVALUATOR has given a score of 8 or higher, respond with "EVALUATOR: Approves idea"\
    Score is given only, if chat history has '**Overall Score' in the message.
    
    AGENTS:
    - CREATOR: Generates creative ideas
    - ENHANCER: Improves and expands on ideas
    - EVALUATOR: Rates ideas on a scale of 1-10
    
    CHAT HISTORY: {{{{$history}}}}
    """
    
    # Termination prompt for evaluator
    termination_prompt = """
    Extract the numerical score from the evaluator's message.
    Return only the number, nothing else.
    {{{{$evaluation}}}}
    """
    
    # Custom result extractor function
    def extract_final_idea(messages):
        # Find the last message from enhancer that was scored highly
        enhancer_messages = [m.to_dict() for m in messages if m.name == "Enhancer"]
        if enhancer_messages:
            return enhancer_messages[-1]
        # Fallback to creator
        creator_messages = [m.to_dict() for m in messages if m.name == "Creator"]
        if creator_messages:
            return creator_messages[-1]
        # Final fallback
        return messages[-1].to_dict()
    
    # Create the debate configuration using Pydantic models
    settings = DebateSettings(
        selection=settings_executor,
        next_action=settings_utility,
        termination=settings_utility
    )
    
    prompts = DebatePrompts(
        speaker_selection=speaker_selection_prompt,
        next_action=next_action_prompt,
        termination_function=termination_prompt
    )
    
    config = DebateConfig(
        kernel=kernel,
        agents=agents,
        settings=settings,
        prompts=prompts,
        result_extractor=extract_final_idea,
        maximum_iterations=8,
        termination_agents=[evaluator]
    )
    
    # Create the debate pattern instance with the config
    return DebatePattern(config=config)


async def run_brainstorming_example(user_id: str, conversation_history: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """
    Example showing how to use a custom debate pattern
    
    Args:
        user_id: User identifier
        conversation_history: Chat history
        
    Yields:
        Status updates and final result
    """
    # Create the brainstorming debate pattern
    brainstorm_debate = await create_brainstorming_debate()
    
    # Initial message to indicate the start of the debate
    initial_message = "CREATOR: Starting brainstorming session"
    
    # Run the debate using our custom pattern
    async for message in brainstorm_debate.run_debate(
        user_id,
        conversation_history,
        initial_message
    ):
        yield message


# Example of creating a very different debate pattern: Problem Solving Trio
async def create_problem_solving_debate() -> DebatePattern:
    """
    Creates a debate pattern for collaborative problem solving with 3 specialized agents:
    - Analyst (breaks down problems)
    - Explorer (proposes multiple solutions)
    - Validator (evaluates solutions for practicality)
    
    Returns:
        A configured DebatePattern instance
    """
    # These YAML files would need to be created
    analyst = create_agent_from_yaml(
        service_id="executor",
        kernel=kernel,
        definition_file_path="agents/problem_solving/analyst.yaml"
    )
    
    explorer = create_agent_from_yaml(
        service_id="executor",
        kernel=kernel,
        definition_file_path="agents/problem_solving/explorer.yaml"
    )
    
    validator = create_agent_from_yaml(
        service_id="executor",
        kernel=kernel,
        definition_file_path="agents/problem_solving/validator.yaml"
    )
    
    agents = [analyst, explorer, validator]
    
    # Define execution settings
    settings_executor = AzureChatPromptExecutionSettings(service_id="executor", temperature=0.5)
    settings_utility = AzureChatPromptExecutionSettings(service_id="utility", temperature=0)
    
    # Speaker selection prompt template
    speaker_selection_prompt = fr"""
    You are the problem-solving collaboration coordinator.

    Select the next speaker who should contribute to solving the problem.
    Return ONLY the agent name from the available agents below.

    Follow this general flow:
    1. ANALYST should speak first to understand and break down the problem
    2. EXPLORER should suggest multiple solutions after analysis
    3. VALIDATOR should evaluate the proposed solutions
    4. Return to ANALYST or EXPLORER based on validation results

    # AVAILABLE AGENTS
    {{{{$agents}}}}

    # CHAT HISTORY
    {{{{$history}}}}
    """
    
    # Next action prompt template
    next_action_prompt = fr"""
    Based on the problem-solving session history below, describe what is happening next.
    
    Use a brief phrase (3-5 words) that includes the agent name, for example:
    "ANALYST: Breaking down problem" or "EXPLORER: Suggesting solutions"
    
    If VALIDATOR approves a solution with a score of 8 or higher, respond with:
    "VALIDATOR: Solution accepted"
    
    AGENTS:
    - ANALYST: Breaks down problems into components
    - EXPLORER: Generates multiple solution approaches
    - VALIDATOR: Evaluates solutions with scores from 1-10
    
    CHAT HISTORY: {{{{$history}}}}
    """
    
    # Termination function prompt
    termination_prompt = """
    Extract the solution score from the validator's assessment.
    Return only the numerical score (1-10), nothing else.
    {{{{$evaluation}}}}
    """
    
    # Create the debate configuration using Pydantic models
    settings = DebateSettings(
        selection=settings_executor,
        next_action=settings_utility,
        termination=settings_utility
    )
    
    prompts = DebatePrompts(
        speaker_selection=speaker_selection_prompt,
        next_action=next_action_prompt,
        termination_function=termination_prompt
    )
    
    # Custom result extraction function
    def extract_best_solution(messages):
        # Get the last validated solution
        explorer_messages = [m.to_dict() for m in messages if m.name == "Explorer"]
        if explorer_messages:
            return explorer_messages[-1]
        # Fallback
        return messages[-1].to_dict()
    
    config = DebateConfig(
        kernel=kernel,
        agents=agents,
        settings=settings,
        prompts=prompts,
        result_extractor=extract_best_solution,
        maximum_iterations=10,
        termination_agents=[validator]
    )
    
    # Return the configured debate pattern
    return DebatePattern(config=config)


async def run_problem_solving_example(user_id: str, conversation_history: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """
    Example showing how to use the problem-solving debate pattern
    
    Args:
        user_id: User identifier
        conversation_history: Chat history
        
    Yields:
        Status updates and final solution
    """
    # Create the problem-solving debate pattern
    problem_solving_debate = await create_problem_solving_debate()
    
    # Initial message to indicate the start of the debate
    initial_message = "ANALYST: Starting problem analysis"
    
    # Run the debate using our problem-solving pattern
    async for message in problem_solving_debate.run_debate(
        user_id,
        conversation_history,
        initial_message
    ):
        yield message