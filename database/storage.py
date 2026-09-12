import os
import aiofiles # Для асинхронного чтения локального кэша, если minio недоступен
from aiobotocore.session import get_session
from botocore.exceptions import ClientError
from metrics.telemetry import log_event

BUCKET_NAME = "agent-prompts"

def get_minio_credentials() -> tuple[str, str, str]:
    """Динамически извлекает параметры MinIO из config.ini с учетом окружения разработки"""
    from main import app_config
    
    minio_cfg = app_config.get("minio", {})
    host = minio_cfg.get("host", "http://localhost")
    port = minio_cfg.get("port", "9000")
    user = minio_cfg.get("user", "marmai_admin")
    
    # Сначала пытаемся взять 'pass' из секции [minio], 
    # если нет — берем напрямую из os.environ, если и там нет — ставим дефолт
    password = minio_cfg.get("pass") or os.environ.get("MINIO_ROOT_PASSWORD", "nJgDOIrMxTXdtlHAePSAZ2")
    
    # Умная подмена хоста для локальной Windows машины
    if "minio_core" in host and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
        
    endpoint_url = f"{host}:{port}"
    return endpoint_url, user, password


async def init_prompt_storage():
    """Асинхронная инициализация бакета и синхронизация системных промптов при старте"""
    endpoint_url, user, password = get_minio_credentials()
    
    print(f"=== [MinIO] Попытка асинхронного подключения к: {endpoint_url} ===")
    
    session = get_session()
    async with session.create_client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=user,
        aws_secret_access_key=password,
        region_name="ru-east-1"
    ) as s3:
        try:
            # Асинхронно проверяем наличие бакета
            await s3.head_bucket(Bucket=BUCKET_NAME)
            print(f"=== [MinIO] Бакет '{BUCKET_NAME}' обнаружен ===")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"=== [MinIO] Бакет '{BUCKET_NAME}' не найден. Создаю новый... ===")
                await s3.create_bucket(Bucket=BUCKET_NAME)
                print(f"=== [MinIO] Бакет '{BUCKET_NAME}' успешно создан! ===")
            else:
                log_event(
                    body=f"MinIO bucket check failed: {str(e)}",
                    event_name="minio_init_error",
                    attributes={"status": "error"}
                )
                raise e

        # Локальные файлы для синхронизации
        local_files = {
            "instructions/system_prompt.md": "system_prompt.md",
            "instructions/architecture.md": "architecture.md",
            "instructions/agent_pipeline.md": "agent_pipeline.md"
        }

        for local_path, s3_key in local_files.items():
            if os.path.exists(local_path):
                try:
                    # Читаем локальный файл асинхронно перед отправкой
                    with open(local_path, "rb") as f:
                        file_data = f.read()
                        
                    await s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=file_data)
                    print(f"✅ [MinIO] Файл {local_path} синхронизирован как {s3_key}")
                except Exception as upload_err:
                    print(f"❌ [MinIO] Ошибка загрузки файла {local_path}: {upload_err}")
            else:
                print(f"⚠️ [MinIO] Локальный файл {local_path} отсутствует на диске!")


async def load_prompt_from_minio(s3_key: str) -> str:
    """Асингулярно скачивает текст промпта из MinIO с фоллбэком на локальный кэш"""
    endpoint_url, user, password = get_minio_credentials()
    
    session = get_session()
    try:
        async with session.create_client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=user,
            aws_secret_access_key=password,
            region_name="ru-east-1"
        ) as s3:
            response = await s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            async with response['Body'] as stream:
                data = await stream.read()
                return data.decode('utf-8')
                
    except Exception as e:
        log_event(
            body=f"Failed to read prompt '{s3_key}' from MinIO, switching to fallback: {str(e)}",
            event_name="minio_read_warning",
            attributes={"status": "warning", "file": s3_key}
        )
        
        # Надежный асинхронный фоллбэк на локальный файл
        local_fallback = f"instructions/{s3_key}"
        if os.path.exists(local_fallback):
            with open(local_fallback, "r", encoding="utf-8") as f:
                return f.read()
        return ""
