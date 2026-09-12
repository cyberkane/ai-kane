import os
import json
import redis.asyncio as aioredis
from metrics.telemetry import logger

# Подключаемся к Dragonfly по внутреннему DNS имени Docker-сети
DRAGONFLY_URL = os.getenv("DRAGONFLY_URL", "redis://ai_dragonfly:6379/0")

print(f"🔄 [Memory] Инициализация подключения к Dragonfly: {DRAGONFLY_URL}...")
redis_client = aioredis.from_url(DRAGONFLY_URL, decode_responses=True)


async def save_chat_history(session_id: str, messages: list) -> bool:
    """Сохраняет полную историю сообщений сессии в Dragonfly в формате JSON с TTL 24 часа."""
    if not session_id:
        return False
    try:
        key = f"marm_chat:{session_id}"
        # Сериализуем сообщения в JSON-строку
        serialized_data = json.dumps(messages, ensure_ascii=False)
        
        # Записываем в Dragonfly и выставляем TTL на 1 сутки (86400 секунд)
        await redis_client.set(key, serialized_data, ex=86400)
        return True
    except Exception as e:
        logger.error(f"❌ [Dragonfly] Ошибка сохранения истории: {e}")
        return False


async def get_chat_history(session_id: str) -> list:
    """Вытаскивает историю сообщений из Dragonfly. Возвращает пустой список, если ключ отсутствует."""
    if not session_id:
        return []
    try:
        key = f"marm_chat:{session_id}"
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return []
    except Exception as e:
        logger.error(f"❌ [Dragonfly] Ошибка извлечения истории: {e}")
        return []


async def clear_chat_history(session_id: str) -> bool:
    """Удаляет сессию из памяти при очистке контекста разработчиком."""
    if not session_id:
        return False
    try:
        key = f"marm_chat:{session_id}"
        await redis_client.delete(key)
        print(f"🧹 [Dragonfly] Контекст сессии {session_id} успешно очищен.")
        return True
    except Exception as e:
        logger.error(f"❌ [Dragonfly] Ошибка удаления сессии: {e}")
        return False
