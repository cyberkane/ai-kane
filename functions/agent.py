import uuid
from fastapi import APIRouter, Request, HTTPException, status
from langchain_core.messages import HumanMessage
from database.agent_graph import agent_app
from metrics.telemetry import log_event

router = APIRouter()

@router.post("/agent/chat")
async def run_agent_graph(request: Request):
    """
    Эндпоинт для запуска LangGraph агента с инструментами.
    Ожидает JSON вида: 
    {
        "message": "Какое сейчас время на сервере?",
        "thread_id": "опциональный_строковый_id_сессии"
    }
    """
    try:
        body = await request.json()
        user_message = body.get("message")
        
        if not user_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'message' field in request body."
            )
            
        # Извлекаем thread_id из запроса или генерируем новый для изоляции сессий памяти
        thread_id = body.get("thread_id", str(uuid.uuid4()))
        config = {"configurable": {"thread_id": thread_id}}
        
        log_event(
            body=f"Invoking LangGraph agent workflow for thread: {thread_id}",
            event_name="agent_graph_start",
            attributes={"thread_id": thread_id, "status": "info"}
        )
        
        # Подготавливаем стартовое состояние для графа
        inputs = {"messages": [HumanMessage(content=user_message)]}
        
        # Асинхронно запускаем выполнение графа LangGraph до тех пор, пока он не дойдет до END
        final_state = await agent_app.ainvoke(inputs, config=config)
        
        # Извлекаем самое последнее сообщение из истории графа (это должен быть финальный ответ AI)
        messages_history = final_state.get("messages", [])
        if not messages_history:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Agent graph execution returned empty state."
            )
            
        last_ai_message = messages_history[-1]
        
        log_event(
            body=f"LangGraph workflow successfully finished for thread: {thread_id}",
            event_name="agent_graph_success",
            attributes={"thread_id": thread_id, "status": "success", "steps_count": len(messages_history)}
        )
        
        # Возвращаем структурированный ответ
        return {
            "status": "success",
            "thread_id": thread_id,
            "response": last_ai_message.content
        }
        
    except Exception as e:
        log_event(
            body=f"Critical failure in agent graph endpoint: {str(e)}",
            event_name="agent_graph_error",
            attributes={"status": "error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while running the agent graph: {str(e)}"
        )