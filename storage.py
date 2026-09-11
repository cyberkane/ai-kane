import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from telemetry import logger # Используем глобальный логгер экосистемы

MINIO_ENDPOINT = os.getenv("MINIO_URL", "http://minio-core:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "marmai")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "nJgDOIrMxTXdtlHAePSAZ2")
BUCKET_NAME = "agent-prompts"

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        config=Config(signature_version="s3v4"),
        region_name="ru-east-1"
    )

def init_prompt_storage():
    logger.info(f"📦 [MinIO] Попытка подключения к хранилищу по адресу: {MINIO_ENDPOINT}...")
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        logger.info(f"📦 [MinIO] Бакет '{BUCKET_NAME}' обнаружен.")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            logger.info(f"📦 [MinIO] Бакет '{BUCKET_NAME}' не найден. Создаю новый...")
            s3.create_bucket(Bucket=BUCKET_NAME)
            logger.info(f"📦 [MinIO] Бакет '{BUCKET_NAME}' успешно создан!")
        else:
            logger.error(f"❌ [MinIO] Ошибка проверки бакета: {e}")
            raise e

    # Синхронизируем локальные инструкции
    local_files = {
        "instructions/system_prompt.md": "system_prompt.md",
        "instructions/architecture.md": "architecture.md",
        "instructions/agent_pipeline.md": "agent_pipeline.md"
    }

    for local_path, s3_key in local_files.items():
        if os.path.exists(local_path):
            try:
                s3.upload_file(local_path, BUCKET_NAME, s3_key)
                logger.info(f"✅ [MinIO] Файл {local_path} загружен как {s3_key}")
            except Exception as upload_err:
                logger.error(f"❌ [MinIO] Ошибка загрузки файла {local_path}: {upload_err}")
        else:
            logger.warning(f"⚠️ [MinIO] Локальный файл {local_path} отсутствует на диске!")

def load_prompt_from_minio(s3_key: str) -> str:
    s3 = get_s3_client()
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        logger.warning(f"⚠️ [MinIO] Не удалось прочесть {s3_key}, использую локальный кэш. Ошибка: {e}")
        local_fallback = f"instructions/{s3_key}"
        if os.path.exists(local_fallback):
            with open(local_fallback, "r", encoding="utf-8") as f:
                return f.read()
        return ""
