

async def receive_ide_event(payload: FileActivityRequest):
    logger.info(
        f"IDE Event: {payload.event_type} на файле {payload.file_path}", 
        extra={"project_id": payload.project_id, "event": payload.event_type}
    )
    
    try:
        # Импортируем нашу функцию из модуля аналитики
        from analytics import log_file_activity
        import asyncio
        
        # Асинхронно отправляем метрику в InfluxDB 3 в таблицу file_activity
        asyncio.create_task(
            log_file_activity(
                project_id=payload.project_id,
                file_path=payload.file_path,
                event_type=payload.event_type,
                language=payload.language,
                cursor_line=payload.cursor_line,
                cursor_column=payload.cursor_column,
                lines_changed=payload.lines_changed,
                file_size_bytes=payload.file_size_bytes
            )
        )
        return {"status": "success", "message": "Метрика file_activity успешно принята шлюзом"}
        
    except Exception as e:
        logger.error(f"Ошибка обработки метрики IDE: {e}")
        raise HTTPException(status_code=500, detail=str(e))