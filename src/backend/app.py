"""
FastAPI backend application for blog post generation using AI debate orchestration.

This module initializes a FastAPI application that exposes endpoints for generating
blog posts using a debate pattern orchestrator, with appropriate logging, tracing,
and metrics configurations.
"""
import json
import logging
import os
from fastapi import FastAPI, Body
from fastapi.responses import StreamingResponse
from patterns.debate import DebateOrchestrator
from patterns.debate_ai_foundry import DebateOrchestrator as DebateOrchestratorAiFoundry
from utils.util import load_dotenv_from_azd, set_up_tracing, set_up_metrics, set_up_logging

load_dotenv_from_azd()
set_up_tracing()
set_up_metrics()
set_up_logging()

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:   %(name)s   %(message)s',
)
logger = logging.getLogger(__name__)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.monitor.opentelemetry.exporter.export').setLevel(logging.WARNING)

# Initialize FastAPI app
app = FastAPI()

logger.info("Diagnostics: %s", os.getenv('SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS'))

@app.post("/blog")
async def http_blog(request_body: dict = Body(...)):
    """
    Generate a blog post about a specified topic using the debate orchestrator.
    
    Args:
        request_body (dict): JSON body containing 'topic', 'user_id', and 'orchestrator_type' fields.
            - topic (str): The subject for the blog post. Defaults to 'Starwars'.
            - user_id (str): Identifier for the user making the request. Defaults to 'default_user'.
            - orchestrator_type (str): Type of orchestrator to use. 'sk' for pure Semantic Kernel agents, 
              'ai_foundry_sk_mix' for 1 Azure AI agent and 1 SK agent. Defaults to 'sk'.
    
    Returns:
        StreamingResponse: A streaming response.
        Chunk can be be either a string or contain JSON. 
        If the chunk is a string it is a status update. 
        JSON will contain the generated blog post content.
    """
    logger.info('API request received with body %s', request_body)

    topic = request_body.get('topic', 'Starwars')
    user_id = request_body.get('user_id', 'default_user')
    orchestrator_type = request_body.get('orchestrator_type', 'sk')
    content = f"Write a blog post about {topic}."

    # Select orchestrator based on request parameter
    if orchestrator_type == 'sk':
        orchestrator = DebateOrchestrator()
        logger.info('Using DebateOrchestrator (Two Semantic Kernel agents)')
    else:
        orchestrator = DebateOrchestratorAiFoundry()
        logger.info('Using DebateOrchestratorAiFoundry (One Semantic Kernel agent and one Azure AI Agent)')

    conversation_messages = []
    conversation_messages.append({'role': 'user', 'name': 'user', 'content': content})

    async def doit():
        """
        Asynchronous generator that streams debate orchestrator responses.
        
        Yields:
            str: Chunks of the generated blog post content with newline characters appended.
        """
        async for i in orchestrator.process_conversation(user_id, conversation_messages):
            yield i + '\n'

    return StreamingResponse(doit(), media_type="application/json")