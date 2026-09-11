import os
import logging
import socket  # 
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

otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://ai_monitoring_telegraf:4317")

# Извлекаем чистый хост для проверки (удаляем http:// и порт)
host_to_check = otlp_endpoint.replace("http://", "").split(":")[0]

# Проверяем, виден ли контейнер Telegraf в сети Docker прямо сейчас
telegraf_available = False
try:
    socket.gethostbyname(host_to_check)
    telegraf_available = True
except socket.gaierror:
    # Если имя хоста не найдено, мы не дадим упасть всему приложению!
    print(f"⚠️ [Telemetry] Хост {host_to_check} недоступен в сети Docker. Логи будут выводиться только в консоль.")

# Настройка стандартного модуля logging
logger = logging.getLogger("vault-loader")
logger.setLevel(logging.INFO)

# Если Telegraf онлайн — подключаем gRPC экспорт логов
if telegraf_available:
    try:
        otlp_exporter = OTLPLogExporter(endpoint=otlp_endpoint, insecure=True)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger.addHandler(handler)
        print("🟢 [Telemetry] OpenTelemetry gRPC экспортер успешно подключен к Telegraf!")
    except Exception as e:
        print(f"⚠️ [Telemetry] Не удалось инициализировать OTLPLogExporter: {e}")
else:
    # Фаллбэк: если мониторинг выключен, пишем логи просто в консоль Docker контейнера
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    print("🟡 [Telemetry] Включен локальный режим логирования в консоль (Telegraf оффлайн).")