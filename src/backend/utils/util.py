from io import StringIO
from subprocess import run, PIPE
import os
import logging
from dotenv import load_dotenv
import yaml


from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.azure_ai_inference import AzureAIInferenceChatCompletion
from azure.ai.inference.aio import ChatCompletionsClient
from azure.identity.aio import DefaultAzureCredential

from semantic_kernel.functions import KernelArguments
from semantic_kernel.agents import ChatCompletionAgent

logger = logging.getLogger(__name__)

def load_dotenv_from_azd():
    """
    Loads environment variables from Azure Developer CLI (azd) or .env file.
    
    Attempts to load environment variables using the azd CLI first. 
    If that fails, falls back to loading from a .env file in the current directory.
    """
    result = run("azd env get-values", stdout=PIPE, stderr=PIPE, shell=True, text=True)
    if result.returncode == 0:
        logging.info(f"Found AZD environment. Loading...")
        load_dotenv(stream=StringIO(result.stdout))
    else:
        logging.info(f"AZD environment not found. Trying to load from .env file...")
        load_dotenv()


def create_chat_model(service_id, deployment_name, endpoint=None, api_version=None):
    """
    Creates a single AzureAIInferenceChatCompletion service using DefaultAzureCredential for authentication.
    
    Args:
        service_id (str): Identifier for the service to be used in Semantic Kernel.
        deployment_name (str): Azure OpenAI deployment name for the model.
        endpoint (str, optional): Azure OpenAI endpoint URL. If None, will be read from AZURE_OPENAI_ENDPOINT env variable.
        api_version (str, optional): Azure OpenAI API version. If None, will be read from AZURE_OPENAI_API_VERSION env variable.
        
    Returns:
        AzureAIInferenceChatCompletion: A service for use with Semantic Kernel, or None if required configuration is missing.
    """
    endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION")
    
    # Return None if required configuration is missing
    if not endpoint or not api_version or not deployment_name:
        logging.warning(f"Missing required OpenAI configuration for {service_id}. Endpoint, API version or deployment name not provided.")
        return None
    
    credential = DefaultAzureCredential()
    
    return AzureAIInferenceChatCompletion(
        ai_model_id=service_id,
        service_id=service_id,
        client=ChatCompletionsClient(
            endpoint=f"{str(endpoint).strip('/')}/openai/deployments/{deployment_name}",
            api_version=api_version,
            credential=credential,
            credential_scopes=["https://cognitiveservices.azure.com/.default"],
        )
    )

def create_agent_from_yaml(kernel, service_id, definition_file_path, reasoning_effort=None):
    """
    Creates a ChatCompletionAgent from a YAML definition file.
    
    Args:
        kernel: The Semantic Kernel instance
        service_id: The service ID to use for the agent
        definition_file_path: Path to the YAML file containing agent definition
        reasoning_effort: Optional reasoning effort parameter for OpenAI models
        
    Returns:
        ChatCompletionAgent: Configured agent instance
        
    The YAML definition should include name, description, instructions, 
    temperature, and included_plugins.
    """
        
    with open(definition_file_path, 'r', encoding='utf-8') as file:
        definition = yaml.safe_load(file)
        
    settings = AzureChatPromptExecutionSettings(
            temperature=definition.get('temperature', 0.5),
            function_choice_behavior=FunctionChoiceBehavior.Auto(
                filters={"included_plugins": definition.get('included_plugins', [])}
            ))

    # Reasoning model specifics
    model_id = kernel.get_service(service_id=service_id).ai_model_id
    if model_id.lower().startswith("o"):
        settings.temperature = None
        settings.reasoning_effort = reasoning_effort
        
    agent = ChatCompletionAgent(
        service=kernel.get_service(service_id=service_id),
        kernel=kernel,
        arguments=KernelArguments(settings=settings),
        name=definition['name'],
        description=definition['description'],
        instructions=definition['instructions']
    )
    
    return agent
