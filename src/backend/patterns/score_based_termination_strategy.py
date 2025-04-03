import logging
import inspect
from typing import List, Any

from semantic_kernel import Kernel
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.functions import KernelFunctionFromPrompt, KernelArguments

logger = logging.getLogger(__name__)


class ScoreBasedTerminationStrategy(TerminationStrategy):
    """Terminates the agent conversation when evaluation score exceeds a threshold."""

    kernel: Kernel
    agents: List[Any]
    maximum_iterations: int = 6
    threshold: float = 8.0
    iteration: int = 0
    termination_function: KernelFunctionFromPrompt


    async def should_agent_terminate(self, agent, history):
        self.iteration += 1
        logger.info(f"Iteration: {self.iteration} of {self.maximum_iterations}")

        arguments = KernelArguments()
        arguments["evaluation"] = history[-1].content

        res_val = await self.kernel.invoke(function=self.termination_function, arguments=arguments)
        logger.info(f"Critic Evaluation: {res_val}")

        try:
            should_terminate = float(str(res_val)) >= self.threshold
        except ValueError:
            logger.error(f"Should terminate error: ValueError parsing '{res_val}'")
            should_terminate = False

        logger.info(f"Should terminate: {should_terminate}")
        return should_terminate
