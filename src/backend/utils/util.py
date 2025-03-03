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


def set_up_tracing():
    exporters = []
    exporters.append(AzureMonitorTraceExporter.from_connection_string(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))
    if (local_endpoint):
        exporters.append(OTLPSpanExporter(endpoint=local_endpoint))

    tracer_provider = TracerProvider(resource=telemetry_resource)
    for trace_exporter in exporters:
        tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    set_tracer_provider(tracer_provider)


def set_up_metrics():
    exporters = []
    if (local_endpoint):
        exporters.append(OTLPMetricExporter(endpoint=local_endpoint))
    exporters.append(AzureMonitorMetricExporter.from_connection_string(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))

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


def set_up_logging():
    exporters = []
    exporters.append(AzureMonitorLogExporter(connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))

    if (local_endpoint):
        exporters.append(OTLPLogExporter(endpoint=local_endpoint))
    # exporters.append(ConsoleLogExporter())

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
        """A filter to not process records from semantic_kernel."""

        # These are the namespaces that we want to exclude from logging for the purposes of this demo.
        namespaces_to_exclude: list[str] = [
            # "semantic_kernel.functions.kernel_plugin",
            "semantic_kernel.prompt_template.kernel_prompt_template",
            # "semantic_kernel.functions.kernel_function",
            "azure.monitor.opentelemetry.exporter.export._base",
            "azure.core.pipeline.policies.http_logging_policy"
        ]

        def filter(self, record):
            return not any([record.name.startswith(namespace) for namespace in self.namespaces_to_exclude])

    # FILTER - WHAT TO LOG - EXPLICITLY
    # handler.addFilter(logging.Filter("semantic_kernel"))
    handler.addFilter(KernelFilter())

# --------------------------------------------
# UTILITY - CREATES an agent based on YAML definition
# --------------------------------------------
def create_agent_from_yaml(kernel, service_id, definition_file_path, reasoning_effort=None):
        
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
    
async def describe_next_action(kernel, settings, messages):
        next_action = await kernel.invoke_prompt(
            function_name="describe_next_action",
            prompt=f"""
            Provided the following chat history, what is next action in the agentic chat? 
            
            Provide three word summary.
            Always indicate WHO takes the action, for example: WRITER: Writes revises draft
            OBS! CRITIC cannot take action, only to evaluate the text and provide a score.
            
            IF the last entry is from CRITIC and the score is above 8 - you MUST respond with "CRITIC: Approves the text."
            
            AGENTS:
            - WRITER: Writes and revises the text
            - CRITIC: Evaluates the text and provides scroring from 1 to 10
            
            AGENT_CHAT: {messages}
            
            """,
            settings=settings
        )
        return next_action