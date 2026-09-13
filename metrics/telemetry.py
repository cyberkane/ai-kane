import logging
import os
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger("fastapi-app")
logger.setLevel(logging.INFO)

def init_otel_logging(telegraf_host: str, telegraf_port: str):
    """Инициализирует мост между встроенным logging и OpenTelemetry"""
    
    clean_host = telegraf_host.replace("http://", "").replace("https://", "")
    
    # 2. УМНАЯ ПРОВЕРКА: Если мы запускаем код локально на Windows/Mac, 
    # а в конфиге написано имя docker-контейнера (например, telegraf), 
    # мы автоматически меняем его на localhost, чтобы код не падал.
    if clean_host == "telegraf" and not os.path.exists("/.dockerenv"):
        print("=== [OpenTelemetry] Обнаружен локальный запуск. Меняем 'telegraf' на 'localhost' ===")
        clean_host = "localhost"
        
    otlp_endpoint = f"{clean_host}:{telegraf_port}"
    
    resource = Resource.create(attributes={
        "service.name": "fastapi-backend",
        "service.version": "1.0.0",
        "deployment.environment": os.environ.get("ENVIRONMENT", "development")
    })
    
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
    
    exporter = OTLPLogExporter(endpoint=otlp_endpoint, insecure=True)
    
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    
    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

    logger.addHandler(handler)
    print(f"=== [OpenTelemetry] Мост логов успешно настроен на {otlp_endpoint} ===")


def log_event(body: str, event_name: str, attributes: dict = None):
    """Отправляет структурированный лог с дополнительными атрибутами (extra)"""
    log_attributes = {
        "event.name": event_name,
        "status": attributes.get("status", "info") if attributes else "info"
    }
    if attributes:
        log_attributes.update(attributes)
        
    # В стандартном модуле logging кастомные атрибуты OTel передаются через параметр 'extra'
    logger.info(body, extra=log_attributes)