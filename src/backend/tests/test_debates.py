import logging

import pytest
import asyncio
import os

from patterns.debate_examples import run_brainstorming_example, run_problem_solving_example
from utils.util import load_dotenv_from_azd,set_up_tracing, set_up_metrics, set_up_logging


load_dotenv_from_azd()

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

# Skip tests if environment variables for AI services aren't properly set up
required_env_vars = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_VERSION",
    "EXECUTOR_AZURE_OPENAI_DEPLOYMENT_NAME",
    "UTILITY_AZURE_OPENAI_DEPLOYMENT_NAME"
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
service_env_ready = len(missing_vars) == 0

@pytest.mark.skipif(not service_env_ready, 
                    reason=f"Required environment variables not set: {', '.join(missing_vars)}")
@pytest.mark.asyncio(loop_scope="module")
async def test_run_brainstorming_example():
    """Integration test that runs a real brainstorming debate"""
    # Test data
    user_id = "test-integration-user"
    conversation_history = [
        {"role": "user", "content": "I need ideas for a mobile app that helps people reduce food waste."}
    ]
    
    # Run the example with real services
    results = []
    try:
        count = 0
        async for message in run_brainstorming_example(user_id, conversation_history):
            results.append(message)
            print(f"Message received: {message}")
            count += 1
        
        # Verify we got some results back
        assert len(results) > 0

        
    except Exception as e:
        pytest.fail(f"Integration test failed: {str(e)}")


@pytest.mark.skipif(not service_env_ready, 
                    reason=f"Required environment variables not set: {', '.join(missing_vars)}")
@pytest.mark.asyncio(loop_scope="module")
async def test_run_problem_solving_example():
    """Integration test that runs a real problem-solving debate"""
    # Test data
    user_id = "test-integration-user"
    conversation_history = [
        {"role": "user", "content": "How can we optimize the checkout process for an e-commerce website to reduce cart abandonment?"}
    ]
    
    # Run the example with real services
    results = []
    try:
        count = 0
        async for message in run_problem_solving_example(user_id, conversation_history):
            results.append(message)
            print(f"Message received: {message}")
            count += 1
            
        
        # Verify we got some results back
        assert len(results) > 0

        
    except Exception as e:
        pytest.fail(f"Integration test failed: {str(e)}")


if __name__ == "__main__":
    # For manual testing
    asyncio.run(test_run_brainstorming_example(None))
    # asyncio.run(test_run_problem_solving_example(None))