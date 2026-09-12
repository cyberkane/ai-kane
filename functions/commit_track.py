import asyncio
from analytics import log_vcs_history

async def receive_vcs_commit(payload: PS.VcsCommitRequest):
    logger.info(
        f"Git Commit: [{payload.branch}] {payload.commit_hash} от {payload.author}", 
        extra={"commit": payload.commit_hash, "author": payload.author}
    )
    print(f"📋 [VCS Gateway] Получен новый коммит: {payload.commit_hash}. Запись в vcs_history...")
    
    try:
        asyncio.create_task(
            log_vcs_history(
                project_id=payload.project_id,
                commit_hash=payload.commit_hash,
                author=payload.author,
                branch=payload.branch,
                commit_message=payload.commit_message,
                files_added=payload.files_added,
                files_modified=payload.files_modified,
                insertions=payload.insertions,
                deletions=payload.deletions
            )
        )
        return {"status": "success", "message": f"Коммит {payload.commit_hash} успешно залогирован в vcs_history"}
        
    except Exception as e:
        logger.error(f"❌ Ошибка эндпоинта VCS коммитов: {e}")
        raise HTTPException(status_code=500, detail=str(e))
