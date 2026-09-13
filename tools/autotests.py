import os
import time
import httpx
import asyncio
import aiofiles  # Библиотека для асинхронной работы с файловой системой
from metrics.telemetry import log_event

def get_ollama_url() -> tuple[str, str]:
    """Извлекает адрес Ollama из глобального конфига"""
    from main import app_config
    chat_cfg = app_config.get("chat", {})
    host = chat_cfg.get("host", "http://localhost")
    port = chat_cfg.get("port", "11434")
    model = chat_cfg.get("model", "llama3.1:8b")
    
    if "ollama_core" in host and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
    return f"{host}:{port}/api/chat", model

async def generate_autotest_for_file(file_path: str) -> str:
    """
    Асинхронно генерирует новые pytest-тесты для Python-файла.
    Автоматически нормализует абсолютные Linux-пути в относительные.
    """
    # УМНАЯ НОРМАЛИЗАЦИЯ: Если прилетел абсолютный путь вроде /home/user/.../functions/chat.py,
    # мы вырезаем из него только хвостик начиная с ключевых папок проекта
    for marker in ["functions/", "database/", "tools/", "metrics/"]:
        if marker in file_path:
            file_path = file_path[file_path.find(marker):]
            break
            
    # Дополнительная очистка от лидирующих слэшей
    file_path = file_path.lstrip("/")

    if not os.path.exists(file_path):
        return f"❌ [Autotest Gen] Файл '{file_path}' не найден на диске. Проверьте путь."

    log_event(
        body=f"Starting autonomous test generation for: {file_path}",
        event_name="autotest_generation_start",
        attributes={"target_file": file_path}
    )
    
    start_time = time.perf_counter()

    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        source_code = await f.read()

    system_instruction = (
        "Ты — ведущий инженер по автоматизации тестирования на Python (QA Automation Senior).\n"
        "Твоя задача — написать качественные, современные и покрывающие все крайние случаи автотесты "
        "с использованием библиотеки `pytest`.\n"
        "ПРАВИЛО: Возвращай ИСКЛЮЧИТЕЛЬНО чистый код Python без каких-либо объяснений, "
        "без markdown-разметки (не пиши ```python) и без лишнего текста. Только рабочий код тестов."
    )
    
    user_prompt = f"Напиши pytest-тесты для следующего кода:\n\n{source_code}"
    chat_url, model_name = get_ollama_url()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                chat_url,
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False
                },
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()

        test_code = result.get("message", {}).get("content", "").strip()

        if test_code.startswith("```"):
            test_code = "\n".join(test_code.split("\n")[1:-1])

        # Формируем имя для файла тестов. 
        # Если файл лежал в подпапке (например, functions/chat.py), берем только имя файла
        base_name = os.path.basename(file_path)
        test_file_name = f"test_{base_name}"
        test_file_path = os.path.join("tests", test_file_name)

        os.makedirs("tests", exist_ok=True)
        async with aiofiles.open(test_file_path, mode='w', encoding='utf-8') as f:
            await f.write(test_code)

        generation_time = round(time.perf_counter() - start_time, 3)
        log_event(
            body=f"Autotests successfully generated for {file_path} in {generation_time}s",
            event_name="autotest_generation_success",
            attributes={"status": "success", "generated_path": test_file_path}
        )

        return (
            f"✅ [Autotest Gen] Автотесты для файла '{file_path}' успешно сгенерированы!\n"
            f"📂 Файл сохранен как: {test_file_path}\n"
            f"⏱️ Время генерации: {generation_time} сек."
        )

    except Exception as e:
        log_event(
            body=f"Autotest generation failed: {str(e)}",
            event_name="autotest_generation_error",
            attributes={"status": "error"}
        )
        return f"❌ [Autotest Gen] Критическая ошибка при генерации тестов: {str(e)}"
