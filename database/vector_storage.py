import os
import time
import httpx
from qdrant_client import AsyncQdrantClient  # Используем асинхронный клиент
from qdrant_client.models import PointStruct, VectorParams, Distance
from metrics.telemetry import log_event

COLLECTION_NAME = "marmai_knowledge"

def get_service_urls() -> tuple[str, str, str]:
    """Динамически извлекает URL-адреса из глобального конфига с учетом локального запуска"""
    from main import app_config
    
    vectors_cfg = app_config.get("vectors", {})
    v_host = vectors_cfg.get("host", "http://localhost")
    v_port = vectors_cfg.get("port", "6333")
    
    embed_cfg = app_config.get("embeder", {})
    e_host = embed_cfg.get("host", "http://localhost")
    e_port = embed_cfg.get("port", "11436")
    embed_model = embed_cfg.get("model", "nomic-embed-text")
    
    if not os.path.exists("/.dockerenv"):
        if "qdrant" in v_host:
            v_host = "http://localhost"
        if "nomic" in e_host:
            e_host = "http://localhost"
            
    qdrant_url = f"{v_host}:{v_port}"
    embedder_url = f"{e_host}:{e_port}/v1/embeddings" 
    
    return qdrant_url, embedder_url, embed_model


async def get_text_embedding(text: str) -> list[float]:
    """Асинхронно генерирует вектор через наш защищенный embedder эндпоинт."""
    _, embedder_url, embed_model = get_service_urls()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                embedder_url,
                json={"model": embed_model, "input": text},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return result.get("data", [{}])[0].get("embedding", [])
    except Exception as e:
        log_event(
            body=f"Failed to generate text embedding: {str(e)}",
            event_name="vector_generation_error",
            attributes={"status": "error", "model": embed_model}
        )
        return []


async def init_qdrant_collection() -> bool:
    """Проверяет существование коллекции в Qdrant и создаёт её, если она отсутствует"""
    qdrant_url, _, _ = get_service_urls()
    
    try:
        # ИСПРАВЛЕНО: Создаем клиент напрямую, без async with
        client = AsyncQdrantClient(url=qdrant_url)
        collection_exists = await client.collection_exists(collection_name=COLLECTION_NAME)
        
        if not collection_exists:
            print(f"=== [Qdrant] Коллекция '{COLLECTION_NAME}' не найдена. Создаём... ===")
            await client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=768, 
                    distance=Distance.COSINE
                )
            )
            log_event(
                body=f"Successfully created Qdrant collection: {COLLECTION_NAME}",
                event_name="qdrant_collection_created",
                attributes={"collection_name": COLLECTION_NAME, "status": "success"}
            )
            print(f"=== [Qdrant] Коллекция '{COLLECTION_NAME}' успешно создана! ===")
        else:
            print(f"=== [Qdrant] Коллекция '{COLLECTION_NAME}' уже существует. Шаг пропущен. ===")
            
        await client.close() # Закрываем клиент после выполнения
        return True
    except Exception as e:
        log_event(
            body=f"Failed to initialize Qdrant collection: {str(e)}",
            event_name="qdrant_init_error",
            attributes={"status": "error"}
        )
        print(f"❌ === [Qdrant] Ошибка инициализации коллекции: {e} ===")
        return False


async def save_knowledge_point(point_id: int, title: str, content_text: str, category: str) -> bool:
    """Превращает текст в вектор и асинхронно сохраняет его в Qdrant."""
    qdrant_url, _, _ = get_service_urls()
    
    vector = await get_text_embedding(content_text)
    if not vector:
        return False
        
    try:
        # ИСПРАВЛЕНО: Прямое создание клиента
        client = AsyncQdrantClient(url=qdrant_url)
        point = PointStruct(
            id=int(point_id),
            vector=vector,
            payload={
                "title": str(title),
                "content_text": str(content_text),
                "category": str(category)
            }
        )
        
        await client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point]
        )
        await client.close()
            
        log_event(
            body=f"Knowledge point '{title}' successfully saved to Qdrant",
            event_name="qdrant_upsert_success",
            attributes={"point_id": point_id, "category": category, "status": "success"}
        )
        return True
        
    except Exception as err:
        log_event(
            body=f"Qdrant upsert operation failed: {str(err)}",
            event_name="qdrant_upsert_error",
            attributes={"status": "error", "point_id": point_id}
        )
        return False


async def search_similar_knowledge(query_text: str, limit: int = 2) -> str:
    """Асинхронный семантический поиск в Qdrant для контекста RAG."""
    qdrant_url, _, _ = get_service_urls()
    
    query_vector = await get_text_embedding(query_text)
    if not query_vector:
        return ""
        
    try:
        # ИСПРАВЛЕНО: Прямое создание клиента
        client = AsyncQdrantClient(url=qdrant_url)
        search_results = await client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=limit
        )
        await client.close()
            
        if not search_results:
            return ""
            
        context_chunks = []
        for hit in search_results:
            payload = hit.payload
            context_chunks.append(
                f"--- Документ: {payload.get('title')} (Категория: {payload.get('category')}) ---\n"
                f"{payload.get('content_text')}"
            )
            
        log_event(
            body=f"Semantic search completed. Found {len(search_results)} matches",
            event_name="qdrant_search_success",
            attributes={"matches_count": len(search_results), "status": "success"}
        )
        return "\n\n".join(context_chunks)
        
    except Exception as err:
        log_event(
            body=f"Qdrant semantic search failed: {str(err)}",
            event_name="qdrant_search_error",
            attributes={"status": "error"}
        )
        return ""
