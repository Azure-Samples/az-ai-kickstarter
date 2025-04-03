"""
Utility module for Azure AI Accelerator application.

This module provides helper functions for:
- Environment configuration
- OpenTelemetry setup for observability (tracing, metrics, and logging)
- Agent creation from YAML definitions
- Workflow utilities for agent interactions
"""

from io import StringIO
from subprocess import run, PIPE
import os
import logging
from dotenv import load_dotenv
import yaml

from opentelemetry.sdk.resources import Resource
from opentelemetry._logs import set_logger_provider
from opentelemetry.metrics import set_meter_provider
from opentelemetry.trace import set_tracer_provider

from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    # ConsoleLogExporter
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.view import DropAggregation, View
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
    # ConsoleMetricExporter
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    # ConsoleSpanExporter
)
from opentelemetry.semconv.resource import ResourceAttributes

from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from azure.monitor.opentelemetry.exporter import (
    AzureMonitorLogExporter,
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)

from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings

from semantic_kernel.functions import KernelArguments
from semantic_kernel.agents import ChatCompletionAgent

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

telemetry_resource = Resource.create({ResourceAttributes.SERVICE_NAME: os.getenv("AZURE_RESOURCE_GROUP","ai-accelerator")})

# Set endpoint to the local Aspire Dashboard endpoint to enable local telemetry - DISABLED by default
local_endpoint = None
# local_endpoint = "http://localhost:4317"

# Track telemetry setup state to prevent duplicate registrations
_telemetry_initialized = {
    'tracing': False,
    'metrics': False,
    'logging': False
}

def set_up_tracing():
    """
    Sets up exporters for Azure Monitor and optional local telemetry.
    Will configure local exporters even if Application Insights is not configured.
    """
    # Skip if already initialized
    if _telemetry_initialized['tracing']:
        logging.info("Tracing already initialized, skipping setup.")
        return
        
    exporters = []
    
    # Add Azure Monitor exporter if connection string is available
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        exporters.append(AzureMonitorTraceExporter.from_connection_string(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))
    
    # Add local exporter if local_endpoint is configured
    if local_endpoint:
        exporters.append(OTLPSpanExporter(endpoint=local_endpoint))
    
    # Skip setup completely if no exporters are configured
    if not exporters:
        logging.info("No telemetry exporters configured. Skipping tracing setup.")
        return
        
    tracer_provider = TracerProvider(resource=telemetry_resource)
    for trace_exporter in exporters:
        tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    set_tracer_provider(tracer_provider)
    
    _telemetry_initialized['tracing'] = True
    logging.info("Tracing initialized successfully.")


def set_up_metrics():
    """
    Configures metrics collection with OpenTelemetry.
    Configures views to filter metrics to only those starting with "semantic_kernel".
    Will configure local exporters even if Application Insights is not configured.
    """
    # Skip if already initialized
    if _telemetry_initialized['metrics']:
        logging.info("Metrics already initialized, skipping setup.")
        return
        
    exporters = []
    
    # Add local exporter if local_endpoint is configured
    if local_endpoint:
        exporters.append(OTLPMetricExporter(endpoint=local_endpoint))
    
    # Add Azure Monitor exporter if connection string is available
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        exporters.append(AzureMonitorMetricExporter.from_connection_string(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))
    
    # Skip setup completely if no exporters are configured
    if not exporters:
        logging.info("No telemetry exporters configured. Skipping metrics setup.")
        return

    metric_readers = [PeriodicExportingMetricReader(exporter, export_interval_millis=5000) for exporter in exporters]

    meter_provider = MeterProvider(
        metric_readers=metric_readers,
        resource=telemetry_resource,
        views=[
            # Dropping all instrument names except for those starting with "semantic_kernel"
            View(instrument_name="*", aggregation=DropAggregation()),
            View(instrument_name="semantic_kernel*"),
        ],
    )
    set_meter_provider(meter_provider)
    
    _telemetry_initialized['metrics'] = True
    logging.info("Metrics initialized successfully.")


def set_up_logging():
    """
    Configures logging with OpenTelemetry.
    Adds filters to exclude specific namespace logs for cleaner output.
    Will configure local exporters even if Application Insights is not configured.
    """
    # Skip if already initialized
    if _telemetry_initialized['logging']:
        logging.info("Logging already initialized, skipping setup.")
        return
        
    exporters = []
    
    # Add Azure Monitor exporter if connection string is available
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        exporters.append(AzureMonitorLogExporter(connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))
    
    # Add local exporter if local_endpoint is configured
    if local_endpoint:
        exporters.append(OTLPLogExporter(endpoint=local_endpoint))
    
    # Skip setup completely if no exporters are configured
    if not exporters:
        logging.info("No telemetry exporters configured. Skipping logging setup.")
        return
    
    logger_provider = LoggerProvider(resource=telemetry_resource)
    set_logger_provider(logger_provider)

    handler = LoggingHandler()

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    for log_exporter in exporters:
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

    # FILTER - WHAT NOT TO LOG
    class KernelFilter(logging.Filter):
        """
        A filter to exclude logs from specific semantic_kernel namespaces.
        
        Prevents excessive logging from specified module namespaces to reduce noise.
        """
        # These are the namespaces that we want to exclude from logging for the purposes of this demo.
        namespaces_to_exclude: list[str] = [
            # "semantic_kernel.functions.kernel_plugin",
            "semantic_kernel.prompt_template.kernel_prompt_template",
            # "semantic_kernel.functions.kernel_function",
            "azure.monitor.opentelemetry.exporter.export._base",
            "azure.core.pipeline.policies.http_logging_policy",
            "opentelemetry.sdk.metrics._internal" # Filter out duplicated instrument warnings
        ]

        def filter(self, record):
            return not any([record.name.startswith(namespace) for namespace in self.namespaces_to_exclude])

    # FILTER - WHAT TO LOG - EXPLICITLY
    # handler.addFilter(logging.Filter("semantic_kernel"))
    handler.addFilter(KernelFilter())
    
    _telemetry_initialized['logging'] = True
    logging.info("Logging initialized successfully.")
    
# --------------------------------------------
# UTILITY - CREATES an agent based on YAML definition
# --------------------------------------------
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

    # Resoning model specifics
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
