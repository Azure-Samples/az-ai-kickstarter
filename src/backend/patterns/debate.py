import json
import datetime
import inspect
import json
import logging
from typing import List, Dict, AsyncGenerator, Callable, Optional, Any

from opentelemetry.trace import get_tracer
from patterns.score_based_termination_strategy import ScoreBasedTerminationStrategy
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from semantic_kernel.agents import AgentGroupChat
from semantic_kernel.agents.strategies import KernelFunctionSelectionStrategy
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.functions import KernelFunctionFromPrompt, KernelArguments
from utils.util import load_dotenv_from_azd

load_dotenv_from_azd()
logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


class DebateSettings(BaseModel):
    """Configuration settings for a debate pattern."""
    selection: Optional[AzureChatPromptExecutionSettings] = None
    next_action: Optional[AzureChatPromptExecutionSettings] = None 
    termination: Optional[AzureChatPromptExecutionSettings] = None


class DebatePrompts(BaseModel):
    """Prompt templates used in the debate pattern."""
    speaker_selection: str = Field(..., description="Template for selecting the next speaker")
    next_action: str = Field(..., description="Template for describing the next action")
    termination_function: Optional[str] = Field(None, description="Optional prompt for termination evaluation")

    @field_validator('speaker_selection', 'next_action')
    @classmethod
    def validate_prompts(cls, v: str, info: ValidationInfo) -> str:
        """Validate that prompts are not empty."""
        if not v or not v.strip():
            raise ValueError(f"Prompt template '{info.field_name}' cannot be empty")
        return v


class DebateConfig(BaseModel):
    """Complete configuration for a debate pattern."""
    kernel: Any = Field(..., description="The Semantic Kernel instance")
    agents: List[Any] = Field(..., min_length=1, description="List of agent instances")
    settings: DebateSettings = Field(..., description="Execution settings for different prompts")
    prompts: DebatePrompts = Field(..., description="Prompt templates for the debate")
    result_extractor: Optional[Callable] = Field(None, description="Optional function to extract final result")
    maximum_iterations: int = Field(6, ge=1, description="Maximum number of debate iterations")
    termination_agents: Optional[List[Any]] = Field(None, description="Optional list of agents to use for termination")
    
    @model_validator(mode='after')
    def check_termination_agents(self) -> 'DebateConfig':
        """Validate termination agents are in the agent list."""
        if self.termination_agents:
            agent_names = {agent.name for agent in self.agents}
            for agent in self.termination_agents:
                if agent.name not in agent_names:
                    raise ValueError(f"Termination agent {agent.name} not found in main agents list")
        return self
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class DebatePattern:
    """
    A configurable pattern for orchestrating debates between AI agents.
    
    This class encapsulates the debate pattern, allowing it to be customized
    with different agents, selection strategies, and termination conditions.
    """
    
    def __init__(
        self,
        config: DebateConfig
    ):
        """
        Initialize a new DebatePattern.
        
        Args:
            config: Complete configuration for the debate pattern
        """
        self.config = config
        self.kernel = config.kernel
        self.agents = config.agents
        self.settings = config.settings
        self.maximum_iterations = config.maximum_iterations
        self.termination_agents = config.termination_agents or []
        self.result_extractor = config.result_extractor
        
        # Initialize the agent group chat
        self._setup_agent_group_chat()
        
    def _setup_agent_group_chat(self):
        """Configure the agent group chat with selection and termination strategies."""

        # Create selection function
        selection_function = KernelFunctionFromPrompt(
            function_name="SpeakerSelector",
            prompt_execution_settings=self.settings.selection,
            prompt=inspect.cleandoc(self.config.prompts.speaker_selection)
        )
        
        # Selection strategy with parser
        def parse_selection_output(output):
            logger.info("------- Speaker selected: %s", output)
            if output.value is not None:
                return output.value[0].content
            return self.agents[0].name  # Default to first agent
            
        selection_strategy = KernelFunctionSelectionStrategy(
            kernel=self.kernel,
            function=selection_function,
            result_parser=parse_selection_output,
            agent_variable_name="agents",
            history_variable_name="history"
        )
        
        # Create termination strategy if prompt is provided
        if self.config.prompts.termination_function:
            termination_function = KernelFunctionFromPrompt(
                function_name="TerminationEvaluator",
                prompt_execution_settings=self.settings.termination,
                prompt=inspect.cleandoc(self.config.prompts.termination_function)
            )
            
            termination_strategy = ScoreBasedTerminationStrategy(
                kernel=self.kernel,
                agents=self.termination_agents or self.agents,
                maximum_iterations=self.maximum_iterations,
                termination_function=termination_function
            )
        else:
            # Simple maximum iterations strategy if no termination prompt
            termination_strategy = ScoreBasedTerminationStrategy(
                kernel=self.kernel,
                agents=self.termination_agents or self.agents,
                maximum_iterations=self.maximum_iterations
            )
        
        # Create agent group chat
        self.agent_group_chat = AgentGroupChat(
            agents=self.agents,
            selection_strategy=selection_strategy,
            termination_strategy=termination_strategy
        )
    
    async def describe_next_action(self, messages):
        """
        Determines the next action in an agent conversation workflow.
        
        Args:
            messages: Conversation history between agents
            
        Returns:
            str: A summary of the next action
        """
        next_action = await self.kernel.invoke_prompt(
            function_name="describe_next_action",
            prompt=inspect.cleandoc(self.config.prompts.next_action),
            settings=self.settings.next_action,
            arguments=KernelArguments(
                history=messages
            )
        )
        return next_action
    
    async def process_conversation(
        self, 
        user_id: str, 
        conversation_messages: List[Dict[str, str]],
        initial_message: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Process a conversation by orchestrating a debate between AI agents.
        
        Args:
            user_id: Unique identifier for the user
            conversation_messages: List of conversation message dictionaries
            initial_message: Optional message to yield at the start
            
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
        await self.agent_group_chat.add_chat_messages(chat_history)
        
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        session_id = f"{user_id}-{current_time}"
        messages = []
        
        # Run the conversation with tracing
        with tracer.start_as_current_span(session_id):
            # Yield initial message if provided
            if initial_message:
                yield initial_message
                
            async for a in self.agent_group_chat.invoke():
                logger.info(f"Agent: {a.to_dict()}")
                messages.append(a.to_dict())
                next_action = await self.describe_next_action(messages)
                logger.info(f"{next_action}")
                yield f"{next_action}"
        
        # Get final response using extractor if provided
        all_messages = list(reversed([item async for item in self.agent_group_chat.get_chat_messages()]))
        
        if self.result_extractor:
            result = self.result_extractor(all_messages)
            yield json.dumps(result)
        else:
            # Default behavior: return last message from first agent
            try:
                result = [r.to_dict() for r in all_messages if r.name == self.agents[0].name][-1]
                yield json.dumps(result)
            except (IndexError, KeyError):
                # Fallback if no messages from first agent
                yield json.dumps(all_messages[0].to_dict() if all_messages else {"content": "No results available"})
    
    async def run_debate(
        self, 
        user_id: str, 
        conversation_history: List[Dict[str, str]],
        initial_message: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Public API: Run a debate for the given conversation history.
        
        Args:
            user_id: Unique identifier for the user
            conversation_history: List of conversation messages
            initial_message: Optional message to yield at debate start
        """
        async for message in self.process_conversation(
            user_id, 
            conversation_history,
            initial_message
        ):
            yield message

