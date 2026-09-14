# -*- coding: utf-8 -*-
import os
import aiobotocore.session
import redis.asyncio as aioredis

# Глобальные константы MinIO S3
BUCKET_NAME = "agent-prompts"
s3_client = None

# Инициализируем асинхронное подключение к Dragonfly
redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)


async def init_prompt_storage():
    """
    Инициализирует MinIO S3, автоматически проверяет локальные файлы 
    на обновления и принудительно синхронизирует их с S3 и ОЗУ Dragonfly.
    """
    global s3_client
    from main import app_config
    
    s3_cfg = app_config.get("s3", {})
    endpoint = f"http://{s3_cfg.get('host', 'localhost')}:{s3_cfg.get('port', '9000')}"
    
    print(f"=== [MinIO] Попытка асинхронного подключения к: {endpoint} ===")
    
    # Сбор ключей из всех возможных источников
    access_key = (
        s3_cfg.get("access_key") or 
        s3_cfg.get("access_key_id") or 
        os.getenv("MINIO_ROOT_USER") or 
        os.getenv("AWS_ACCESS_KEY_ID") or 
        "minioadmin"
    ).strip()
    
    secret_key = (
        s3_cfg.get("secret_key") or 
        s3_cfg.get("secret_key_access") or 
        os.getenv("MINIO_ROOT_PASSWORD") or 
        os.getenv("AWS_SECRET_ACCESS_KEY") or 
        "minioadmin"
    ).strip()
    
    # Маскированная отладка ключей, чтобы увидеть, что реально попало в память
    masked_access = f"{access_key[:3]}***{access_key[-3:]}" if len(access_key) > 6 else access_key
    print(f"🔑 [MinIO Auth Debug] Используется Access Key: {masked_access}")
    
    session = aiobotocore.session.get_session()
    s3_client = session.create_client(
        "s3",
        region_name="us-east-1",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key
    )
    
    try:
        async with s3_client as s3:
            # Проверяем существование бакета
            try:
                await s3.head_bucket(Bucket=BUCKET_NAME)
                print(f"=== [MinIO] Бакет '{BUCKET_NAME}' успешно обнаружен ===")
            except Exception as e:
                # Если head_bucket упал, проверяем ошибку на InvalidAccessKeyId
                err_str = str(e)
                if "InvalidAccessKeyId" in err_str or "Forbidden" in err_str:
                    print(f"❌ [MinIO] Ошибка авторизации. Ключи отклонены сервером.")
                    # Не пытаемся создавать бакет с плохими ключами, выходим из lifespan без падения всего сервера
                    return
                
                print(f"🚀 [MinIO] Бакет '{BUCKET_NAME}' не найден или недоступен. Создаю новый...")
                await s3.create_bucket(Bucket=BUCKET_NAME)
                print(f"✅ [MinIO] Бакет '{BUCKET_NAME}' успешно создан!")

            # --- АВТОМАТИЧЕСКАЯ СИНХРОНИЗАЦИЯ ОБНОВЛЕНИЙ ПРИ СТАРТЕ ---
            print("🔄 [MarmAI Синхронизатор] Проверка локальных файлов на изменения...")
            instructions_dir = "instructions"
            if os.path.exists(instructions_dir):
                for filename in os.listdir(instructions_dir):
                    if filename.endswith(".md"):
                        local_path = os.path.join(instructions_dir, filename)
                        
                        try:
                            with open(local_path, "r", encoding="utf-8") as f:
                                current_content = f.read()
                                
                            cache_key = f"prompt:{filename}"
                            cached_content = await redis_client.get(cache_key)
                            
                            if not cached_content or cached_content != current_content:
                                print(f"⚡ [Синхронизатор] Изменения в '{filename}'! Синхронизация ОЗУ и S3...")
                                await redis_client.set(cache_key, current_content, ex=300)
                                
                                await s3.put_object(
                                    Bucket=BUCKET_NAME,
                                    Key=filename,
                                    Body=current_content.encode('utf-8'),
                                    ContentType="text/plain"
                                )
                                print(f"✅ [Синхронизатор] Файл '{filename}' успешно синхронизирован.")
                        except Exception as sync_err:
                            print(f"⚠️ Ошибка синхронизации файла {filename}: {sync_err}")
    except Exception as lifecycle_err:
        print(f"❌ [MinIO Критическая ошибка инициализации]: {lifecycle_err}")


async def load_prompt_from_minio(filename: str) -> str:
    """
    Загружает текст промпта из папки на диске с автоматическим 
    высокоскоростным кэшированием напрямую в оперативную память Dragonfly.
    """
    cache_key = f"prompt:{filename}"
    
    try:
        # 1. Мгновенное извлечение из памяти Dragonfly
        cached_prompt = await redis_client.get(cache_key)
        if cached_prompt:
            return cached_prompt
    except Exception as cache_err:
        print(f"⚠️ [Dragonfly] Ошибка чтения кэша: {cache_err}")

    # 2. Фоллбэк на чтение реального файла с диска
    local_path = os.path.join("instructions", filename)
    if not os.path.exists(local_path):
        local_path = filename

    print(f"📥 [Storage] Чтение свежей копии файла с диска: '{local_path}'...")
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
    except Exception as e:
        print(f"❌ Ошибка чтения файла промпта {filename}: {e}")
        prompt_text = "Ты — полезный ИИ-ассистент MarmAI. В твоем распоряжении есть инструменты."

    # 3. Кэшируем большой текст инструкций обратно в ОЗУ (TTL 5 минут)
    try:
        if len(prompt_text) > 50:
            await redis_client.set(cache_key, prompt_text, ex=300)
            print(f"✅ [Dragonfly] Промпт '{filename}' (длина: {len(prompt_text)}) успешно кэширован!")
    except Exception as cache_err:
        print(f"⚠️ [Dragonfly] Не удалось записать ключ в ОЗУ: {cache_err}")
        
    return prompt_text
