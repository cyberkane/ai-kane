import os
import json
import httpx
import hvac
import aiofiles
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI(title="AI-Kane Cyber-Cat Agent")

# Настройки секретов и Vault
VAULT_URL = os.getenv("VAULT_URL", "http://ai_vault_core:8200")
VAULT_TOKEN = os.getenv("VAULT_DEV_ROOT_TOKEN_ID")

try:
    vault_client = hvac.Client(url=VAULT_URL, token=VAULT_TOKEN)
    if vault_client.is_authenticated():
        print("🔮 [Vault] Соединение установлено! Мармеладные секреты активны.")
except Exception as e:
    print(f"⚠️ [Vault] Сбой моста: {e}")

# Базовые пути для контейнеров моделей
CHAT_URL = os.getenv("CHAT_LLM_URL", "http://ai_ollama_core:11434/v1")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3.1:8b")
AUTO_URL = os.getenv("AUTOCOMPLETE_LLM_URL", "http://ai_qwen_core:11434/v1")
AUTO_MODEL = os.getenv("AUTOCOMPLETE_MODEL", "qwen2.5-coder:1.5b")

DEFAULT_MARM_PROMPT = (
    "Ты киберкотик, прибывший с далекой Мармеладной планеты. "
    "В твоей речи мягкость мармелада сочетается с точностью квантового компьютера."
)

async def load_system_prompt() -> str:
    prompt_path = "/app/system_prompt.md"
    if not os.path.exists(prompt_path):
        return DEFAULT_MARM_PROMPT
    try:
        async with aiofiles.open(prompt_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            return content.strip() if content.strip() else DEFAULT_MARM_PROMPT
    except Exception:
        return DEFAULT_MARM_PROMPT

# =====================================================================
# НАТИВНЫЙ ЧАТ OLLAMA С АВТО-КОНТЕКСТОМ СТРОК
# =====================================================================
@app.post("/api/chat")
async def ollama_chat_endpoint(request: Request):
    body = await request.json()
    body["model"] = CHAT_MODEL
    
    # 1. Загружаем характер из system_prompt.md
    system_prompt_content = await load_system_prompt()
    
    # 2. КВАНТОВЫЙ ПЕРЕХВАТ КОНТЕКСТА: Сканируем входящий JSON на наличие открытого кода
    active_code_context = ""
    
    # Способ А: Извлекаем из встроенного массива contextItems (если передан)
    context_items = body.get("contextItems", [])
    for item in context_items:
        p_title = item.get("id", {}).get("providerTitle", "").lower()
        if p_title in ["file", "code", "activefile", "currentfile"]:
            f_name = item.get("name", "текущем файле")
            f_content = item.get("content", "")
            if f_content:
                active_code_context += f"\n\n[Файл: {f_name}]\n{f_content}"

    # Способ Б: Если Continue закинул выделенный код прямо в последнее сообщение пользователя
    messages = body.get("messages", [])
    if messages and messages[-1].get("role") == "user":
        user_content = messages[-1].get("content", "")
        # Если в промпте пользователя есть маркеры кода, но нет в системном, дублируем для Llama
        if "```" in user_content and "--- Контекст" not in system_prompt_content:
            print("🐾 [Context Sensor] Зафиксирован встроенный код в запросе пользователя!")

    # 3. Накачиваем матрицу системного промпта актуальным файлом
    if active_code_context:
        print("🐾 [Context Sensor] Автоматически внедряю открытый файл в контекст Llama 3.1!")
        system_prompt_content += (
            f"\n\n⚠️ КВАНТОВЫЙ КОНТЕКСТ РАБОТЫ:"
            f"\nПользователь прямо сейчас открыл в редакторе и редактирует следующий код:"
            f"{active_code_context}\n"
            f"Используй этот код для ответов, рефакторинга и поиска багов без лишних вопросов."
        )

    # 4. Внедряем склеенный промпт в массив сообщений Ollama
    existing_system_msg = next((msg for msg in messages if msg.get("role") == "system"), None)
    
    if existing_system_msg:
        existing_system_msg["content"] = f"{system_prompt_content}\n\n{existing_system_msg['content']}"
    else:
        messages.insert(0, {"role": "system", "content": system_prompt_content})
        
    body["messages"] = messages

    # 5. Стримим ответ напрямую из контейнера Llama 3.1
    async def stream_native_ollama():
        timeout = httpx.Timeout(60.0, connect=10.0)
        native_ollama_url = CHAT_URL.replace("/v1", "")
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{native_ollama_url}/api/chat", json=body) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(stream_native_ollama(), media_type="application/x-ndjson")

# =====================================================================
# НАТИВНОЕ АВТОДОПОЛНЕНИЕ OLLAMA (QWEN)
# =====================================================================
@app.post("/api/generate")
async def ollama_autocomplete_endpoint(request: Request):
    body = await request.json()
    body["model"] = AUTO_MODEL
    
    native_qwen_url = AUTO_URL.replace("/v1", "") + "/api/generate"
    
    async def stream_native_auto():
        timeout = httpx.Timeout(5.0, connect=1.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", native_qwen_url, json=body) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except Exception as e:
                print(f"❌ [Qwen Generate Error] Ошибка стрима автокомплита: {e}")
                yield b"{}\n"

    return StreamingResponse(stream_native_auto(), media_type="application/x-ndjson")

# =====================================================================
# СИСТЕМНЫЙ ПЕРЕХВАТЧИК МЕТОДОВ (/api/show, /api/tags)
# =====================================================================
@app.post("/api/{path:path}")
async def ollama_wildcard_catch(path: str, request: Request):
    native_ollama_url = CHAT_URL.replace("/v1", "")
    try:
        body = await request.json()
    except Exception:
        body = None

    if body is not None:
        if path == "show":
            body["name"] = CHAT_MODEL
            if "model" in body:
                del body["model"]
        else:
            body["model"] = CHAT_MODEL
            body["name"] = CHAT_MODEL

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(f"{native_ollama_url}/api/{path}", json=body)
            return JSONResponse(content=res.json(), status_code=res.status_code)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8977)
