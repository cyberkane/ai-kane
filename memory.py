import os
import logging
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import ConnectionError
from langgraph.checkpoint.redis import RedisSaver

logger = logging.getLogger("vault-loader")

# Загружаем URL Dragonfly из .env (формат: redis://127.0.0.1:6379 или redis://ai_dragonfly:6379)
DRAGONFLY_URL = os.getenv("DRAGONFLY_URL", "redis://ai_dragonfly:6379")

# 1. Синхронный клиент для текущей работы с историей диалогов в FastAPI
try:
    logger.info(f"Инициализация синхронного подключения к Dragonfly...", extra={"redis.url": DRAGONFLY_URL})
    redis_client = Redis.from_url(DRAGONFLY_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Успешное синхронное подключение к Dragonfly (Ping OK)")
except ConnectionError as ce:
    logger.error(f"Не удалось подключиться к Dragonfly (Синхронно): {ce}")
    redis_client = None

# --- 2. АСИНХРОННЫЙ ЧЕКПОИНТЕР ДЛЯ LANGGRAPH ---
try:
    logger.info("Инициализация асинхронного чекпоинтера LangGraph...")
    
    # ПЕРЕДАЕМ СТРОКУ URL НАПРЯМУЮ, библиотека сама сделает startswith() для проверки протокола
    langgraph_checkpointer = RedisSaver(DRAGONFLY_URL)
    
    logger.info("Чекпоинтер LangGraph успешно создан")
except Exception as e:
    logger.error(f"Не удалось инициализировать RedisSaver для LangGraph: {e}")
    langgraph_checkpointer = None

def save_chat_history(session_id: str, role: str, message: str, limit: int = 20):
    """Сохраняет реплику в список истории диалога сессии."""
    if not redis_client:
        logger.warning("Запись невозможна: клиент Dragonfly не инициализирован")
        return False
    
    key = f"chat:{session_id}"
    payload = f"{role}:{message}"
    
    try:
        redis_client.rpush(key, payload)
        redis_client.ltrim(key, -limit, -1)
        return True
    except Exception as e:
        logger.error(f"Ошибка при записи истории в Dragonfly: {e}")
        return False

def get_chat_history(session_id: str):
    """Возвращает список сообщений для указанной сессии."""
    if not redis_client:
        logger.warning("Чтение невозможно: клиент Dragonfly не инициализирован")
        return []
    
    key = f"chat:{session_id}"
    try:
        raw_messages = redis_client.lrange(key, 0, -1)
        history = []
        for msg in raw_messages:
            if ":" in msg:
                role, content = msg.split(":", 1)
                history.append({"role": role, "content": content})
        return history
    except Exception as e:
        logger.error(f"Ошибка при чтении истории из Dragonfly: {e}")
        return []

def clear_chat_history(session_id: str):
    """Удаляет историю сессии из памяти"""
    if redis_client:
        redis_client.delete(f"chat:{session_id}")
