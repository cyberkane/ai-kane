from tools.system_time import get_system_time
from tools.test_runner import run_project_tests
from tools.infra_status import check_infrastructure_status

# Маппинг имен для вызова графом (включает как синхронные, так и асинхронные функции)
TOOLS_REGISTRY = {
    "get_system_time": get_system_time,
    "run_project_tests": run_project_tests,
    "check_infrastructure_status": check_infrastructure_status
}

# Строгие JSON-схемы для Ollama / LangGraph
TOOLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_time",
            "description": "Возвращает точное текущее локальное системное время бэкенда.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_project_tests",
            "description": "Запускает pytest тесты ИИ-агента для проверки работоспособности кода.",
            "parameters": {
                "type": "object",
                "properties": {
                    "module_path": {
                        "type": "string", 
                        "description": "Опциональный путь к файлу или папке тестов (дефолт: 'tests')."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_infrastructure_status",
            "description": "Сканирует порты и проверяет статус здоровья контейнеров Vault, MinIO, InfluxDB, Qdrant и Dragonfly.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]
