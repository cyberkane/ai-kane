# -*- coding: utf-8 -*-
import os
import re
import asyncio
import datetime
import configparser
from fastapi import FastAPI
from dotenv import load_dotenv
from contextlib import asynccontextmanager

#Локальные зависимости
from metrics.telemetry import init_otel_logging, log_event
from functions.chat import router as chat_router
from functions.autocomplete import router as autocomplete_router
from functions.embedder import router as embedder_router
from functions.health import router as health_router
from database.vector_storage import init_qdrant_collection, save_knowledge_point
from database.storage import init_prompt_storage
from functions.agent import router as agent_router
from tools.infra_status import check_infrastructure_status
from tools.test_runner import run_project_tests
from functions.commit_track import router as commit_track_router
from database.vault_storage import fetch_database_secrets
from database.influx_storage import track_agent_telemetry

load_dotenv()
app_config = {}

def replace_env_vars(text: str) -> str:
    pattern = r'\${([^}]+)}'
    
    def match_handler(match):
        var_name = match.group(1)
        return os.environ.get(var_name, f"${{{var_name}}}")
        
    return re.sub(pattern, match_handler, text)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[СТАРТ] Загружаем конфигурацию")
    config = configparser.ConfigParser(
        interpolation=None,
        inline_comment_prefixes=(';',)
    )
    config.read("config.ini", encoding="utf-8")
    
    for section in config.sections():
        app_config[section] = {}
        for key, value in config.items(section):
            clean_value = replace_env_vars(value)
            app_config[section][key] = clean_value

        if section in ['chat', 'autocomplete', 'embeder']:
            host = app_config[section].get('host')
            port = app_config[section].get('port')
            if host and port:
                app_config[section]['api_base'] = f"{host}:{port}"

    # --- АСИНХРОННАЯ ИНТЕГРАЦИЯ VAULT ---
    print("🔐 === [Vault] Подключаемся к сейфу секретов... ===")
    db_secrets = await fetch_database_secrets()

    if db_secrets:
        # Гарантируем наличие секции database в памяти приложения
        if "database" not in app_config:
            app_config["database"] = {}
            
        # Извлекаем токен из Vault и токен из .env для сравнения
        vault_token = db_secrets.get("token", "").strip()
        env_token = os.getenv("INFLUXDB_BOOTSTRAP_TOKEN", "").strip()
        
        # ИСПРАВЛЕНО: Интеллектуальный отбор токена. Если в Vault лежит заглушка "test_token_influx" (меньше 20 символов),
        # а в .env прописан боевой длинный токен, мы защищаем память приложения от перезаписи заглушкой.
        final_token = vault_token
        if len(vault_token) < 20 and len(env_token) > 20:
            final_token = env_token
            print("⚠️ [Vault] В сейфе обнаружен тестовый токен. Автоматически применен боевой токен из .env!")

        app_config["database"]["user"] = db_secrets.get("user", os.getenv("INFLUXDB_BOOTSTRAP_USER", ""))
        app_config["database"]["pass"] = db_secrets.get("pass", os.getenv("INFLUXDB_BOOTSTRAP_PASSWORD", ""))
        app_config["database"]["token"] = final_token
        app_config["database"]["database"] = db_secrets.get("database", os.getenv("INFLUXDB_BOOTSTRAP_DATABASE", "marmai_observability"))
        app_config["database"]["org"] = db_secrets.get("org", os.getenv("INFLUXDB_BOOTSTRAP_ORG", "marmai_planet"))
        
        print("🔐 === [Vault] Секреты InfluxDB успешно инжектированы в память приложения! ===")
    else:
        print("⚠️ === [Vault] Используются базовые значения конфигурации.")

    # Извлекаем секцию мониторинга напрямую
    monitoring_cfg = app_config.get('monitoring')
    
    if monitoring_cfg:
        try:
            init_otel_logging(monitoring_cfg['host'], monitoring_cfg['port'])
            log_event(
                body="Configuration successfully loaded into memory",
                event_name="config_loaded",
                attributes={
                    "loaded_sections_count": len(app_config.keys()),
                    "status": "success"
                }
            )
            
        except Exception as e:
            print(f"=== [Ошибка Телеметрии при старте] {e} ===")
            
    # --- Автоматическая инициализация коллекции Qdrant ---
    await init_qdrant_collection()
    
    # --- Автоматическая инициализация MinIO ---
    await init_prompt_storage()
    
    yield  # В этой точке приложение работает и принимает запросы
    # Логирование остановки приложения (код сработает после выключения сервера)
    if monitoring_cfg:
        try:
            log_event(
                body="Application is shutting down smoothly",
                event_name="app_shutdown",
                attributes={"status": "shutdown"}
            )
            print("=== [OpenTelemetry] Событие остановки успешно отправлено ===")
        except Exception as e:
            print(f"=== [Ошибка Телеметрии при остановке] {e} ===")

# --- Код при выполнении приложения ---
app = FastAPI(title="MarmAI Gateway", lifespan=lifespan)
current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

app.include_router(chat_router, prefix="/v1")
app.include_router(autocomplete_router, prefix="/v1")
app.include_router(embedder_router, prefix="/v1")
app.include_router(agent_router, prefix="/v1")
app.include_router(commit_track_router, prefix="/v1")
app.include_router(health_router)

@app.get("/test-tools")
async def test_all_tools():
    infra_report = await check_infrastructure_status()
    test_report = await run_project_tests("tests")
    return {
        "infrastructure_status": infra_report,
        "pytest_status": test_report
    }

@app.post("/test-add-knowledge")
async def test_add_knowledge():
    # Сохраняем специфическую инструкцию, которой нет в базовых весах Llama 3.1
    success = await save_knowledge_point(
        point_id=1001,
        title="MarmAI Deployment Secret Protocol",
        content_text="Секретный протокол развертывания MarmAI: В случае сбоя Dragonfly, кэш автоматически переключается на резервную реплику, расположенную на сервере node0.marmai.internal.",
        category="infrastructure"
    )
    if success:
        return {"status": "success", "message": "Тестовые знания успешно загружены в Qdrant!"}
    return {"status": "error", "message": "Не удалось загрузить данные"}

@app.get("/config")
async def get_config():
    return {
        "status": "success",
        "time": current_time,
        "data": app_config
    }

@app.get("/health")
async def get_current_time():
    return {
        "status": "success",
        "current_time": current_time
    }