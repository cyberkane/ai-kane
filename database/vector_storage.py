import os
import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from metrics.telemetry import logger

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant_core:6333")
# Для внутренней Docker-сети используем оригинальный порт Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ai_ollama_core:11435")
EMBED_MODEL = "nomic-embed-text:latest"
COLLECTION_NAME = "marmai_knowledge"

# Инициализируем клиент Qdrant
qdrant_client = QdrantClient(url=QDRANT_URL)


async def get_text_embedding(text: str) -> list[float]:
    """Асинхронно генерирует вектор размерности 768 через локальную Ollama."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", [])
    except Exception as e:
        logger.error(f"❌ [Ollama Embeddings] Ошибка генерации вектора: {e}")
        return []


async def save_knowledge_point(point_id: int, title: str, content_text: str, category: str):
    """Превращает текст инструкции в вектор и сохраняет его в marmai_knowledge."""
    try:
        # 1. Получаем реальный математический вектор текста
        vector = await get_text_embedding(content_text)
        
        if not vector:
            logger.error(f"❌ [Qdrant] Не удалось получить вектор для статьи: {title}")
            return False
            
        # 2. Формируем структуру точки Qdrant
        point = PointStruct(
            id=int(point_id),
            vector=vector,
            payload={
                "title": str(title),
                "content_text": str(content_text),
                "category": str(category)
            }
        )
        
        # 3. Сохраняем в Qdrant
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point]
        )
        print(f"✅ [Qdrant] Инструкция '{title}' успешно векторизована и сохранена под ID {point_id}!")
        return True
        
    except Exception as err:
        logger.error(f"❌ [Qdrant] Ошибка upsert операции: {err}")
        return False

async def search_similar_knowledge(query_text: str, limit: int = 2) -> str:
    """Семантический поиск в Qdrant для извлечения контекста знаний (RAG)."""
    try:
        # 1. Получаем математический вектор для поискового запроса пользователя
        query_vector = await get_text_embedding(query_text)
        
        if not query_vector:
            return ""
            
        # 2. Делаем поисковый запрос к коллекции marmai_knowledge
        search_results = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=limit
        )
        
        if not search_results:
            return ""
            
        # 3. Склеиваем найденные куски знаний в один мармеладный текстовый блок
        context_chunks = []
        print(f"🔍 [Qdrant RAG] Найдено {len(search_results)} релевантных совпадений.")
        
        for hit in search_results:
            payload = hit.payload
            context_chunks.append(
                f"--- Документ: {payload.get('title')} (Категория: {payload.get('category')}) ---\n"
                f"{payload.get('content_text')}"
            )
            
        return "\n\n".join(context_chunks)
        
    except Exception as err:
        logger.error(f"❌ [Qdrant RAG] Ошибка семантического поиска: {err}")
        return ""