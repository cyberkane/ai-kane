import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from metrics.telemetry import log_event
from database.vector_storage import save_knowledge_point

router = APIRouter()

# --- 1. СТРОГАЯ PYDANTIC-СХЕМА ВХОДЯЩИХ ДАННЫХ (ENTERPRISE СТАНДАРТ) ---
class VcsCommitRequest(BaseModel):
    project_id: str = Field(..., description="ID или имя репозитория")
    commit_hash: str = Field(..., description="Хеш коммита (SHA)")
    author: str = Field(..., description="Автор изменений")
    branch: str = Field(..., description="Ветка репозитория")
    commit_message: str = Field(..., description="Текст коммита")
    files_added: List[str] = Field(default=[], description="Список добавленных файлов")
    files_modified: List[str] = Field(default=[], description="Список измененных файлов")
    insertions: int = Field(default=0, description="Количество добавленных строк")
    deletions: int = Field(default=0, description="Количество удаленных строк")


# --- 2. АСИНХРОННЫЙ ЭНДПОИНТ ДЛЯ ВЕБХУКОВ Git ---
@router.post("/vcs/commit")
async def receive_vcs_commit(payload: VcsCommitRequest):
    """
    Принимает информацию о коммите, логирует в OpenTelemetry 
    и асинхронно записывает в векторную базу Qdrant для RAG-памяти агента.
    """
    log_event(
        body=f"VCS Webhook received: Commit {payload.commit_hash} on branch {payload.branch}",
        event_name="vcs_webhook_received",
        attributes={
            "commit_hash": payload.commit_hash,
            "author": payload.author,
            "branch": payload.branch,
            "status": "info"
        }
    )
    
    # Склеиваем детальное текстовое описание коммита для семантического векторного поиска
    knowledge_text = (
        f"Коммит в проекте {payload.project_id}. Ветка: {payload.branch}.\n"
        f"Автор: {payload.author}. Хеш: {payload.commit_hash}.\n"
        f"Сообщение коммита: {payload.commit_message}\n"
        f"Добавленные файлы: {', '.join(payload.files_added) if payload.files_added else 'нет'}\n"
        f"Измененные файлы: {', '.join(payload.files_modified) if payload.files_modified else 'нет'}\n"
        f"Статистика кода: +{payload.insertions} строк, -{payload.deletions} строк."
    )
    
    # Генерируем уникальный целочисленный ID для Qdrant на основе времени, 
    # так как Qdrant принимает только int или UUID для Point ID
    point_id = int(time.time() * 1000) & 0xFFFFFFFF 

    try:
        # Асинхронно отправляем скомпилированную историю изменений в Qdrant
        # Наша функция сама вызовет эмбеддер Nomic и сделает неблокирующий upsert
        success = await save_knowledge_point(
            point_id=point_id,
            title=f"Git Commit {payload.commit_hash[:7]}",
            content_text=knowledge_text,
            category="vcs_history"
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to index commit history in vector storage."
            )
            
        log_event(
            body=f"VCS Commit {payload.commit_hash} indexed successfully into Qdrant",
            event_name="vcs_webhook_indexed",
            attributes={"commit_hash": payload.commit_hash, "status": "success"}
        )
        
        return {
            "status": "success", 
            "message": f"Коммит {payload.commit_hash} успешно сохранен в память ИИ-агента."
        }
        
    except Exception as e:
        log_event(
            body=f"VCS tracking failure: {str(e)}",
            event_name="vcs_webhook_error",
            attributes={"status": "error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"VCS tracking critical error: {str(e)}"
        )