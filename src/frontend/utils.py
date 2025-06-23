import logging
import os
from io import StringIO
from subprocess import PIPE, run

from azure.monitor.opentelemetry.exporter import (
    AzureMonitorLogExporter,
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)
from dotenv import load_dotenv
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    # ConsoleLogExporter
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
    # ConsoleMetricExporter
)
from opentelemetry.sdk.metrics.view import DropAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    # ConsoleSpanExporter
)
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import set_tracer_provider
from azure.monitor.opentelemetry import configure_azure_monitor
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from rich.logging import RichHandler

def load_dotenv_from_azd():
    """
    Load environment variables from Azure Developer CLI (azd) or fallback to .env file.

    Attempts to retrieve environment variables using the 'azd env get-values' command.
    If unsuccessful, falls back to loading from a .env file.
    """
    result = run("azd env get-values", stdout=PIPE, stderr=PIPE, shell=True, text=True)
    if result.returncode == 0:
        logging.info("Found AZD environment. Loading...")
        load_dotenv(stream=StringIO(result.stdout))
    else:
        logging.info("AZD environment not found. Trying to load from .env file...")
        load_dotenv()

def setup_telemetry(name):
    logging.info("Setting up logging with RichHandler...")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    #logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    #logging.getLogger('azure.monitor.opentelemetry.exporter.export').setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)

    os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
    os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

    logger.info("Configuring Azure Monitor for OpenTelemetry...")
    application_insights_connection_string = os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
    configure_azure_monitor(connection_string=application_insights_connection_string)

    logging.info("Instrumenting OpenAI SDK for Azure OpenAI...")
    OpenAIInstrumentor().instrument()

    logger.info("Diagnostics: %s", os.getenv('SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS'))
    logger.info("Setting up OpenTelemetry tracer...")
    return trace.get_tracer(name)

