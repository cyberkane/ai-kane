import os
import logging
from dotenv import load_dotenv
from opentelemetry import _logs
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource

load_dotenv()

# --- НАСТРОЙКА OPENTELEMETRY OTLP/gRPC ---
resource = Resource.create(attributes={"service.name": "marmai-backend-service"})
logger_provider = LoggerProvider(resource=resource)
_logs.set_logger_provider(logger_provider)
otlp_endpoint = os.getenv("OTEL_ENDPOINT", "http://ai_monitoring_telegraf:4317")

otlp_exporter = OTLPLogExporter(
    endpoint=otlp_endpoint,
    insecure=True
)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))

# Настройка стандартного модуля logging для интеграции с OpenTelemetry
handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logger = logging.getLogger("vault-loader")
logger.setLevel(logging.INFO)
logger.addHandler(handler)