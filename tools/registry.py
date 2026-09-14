from tools.system_time import get_system_time
from tools.test_runner import run_project_tests
from tools.infra_status import check_infrastructure_status
from tools.autotests import generate_autotest_for_file
from tools.project_mapper import generate_project_architecture
from tools.task_tracker import manage_tasks

# Маппинг имен для вызова графом (включает как синхронные, так и асинхронные функции)
TOOLS_REGISTRY = {
    "get_system_time": get_system_time,
    "run_project_tests": run_project_tests,
    "check_infrastructure_status": check_infrastructure_status,
    "generate_autotest_for_file": generate_autotest_for_file,
    "manage_tasks": manage_tasks,
    "generate_project_architecture": generate_project_architecture
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
    },
    {
        "type": "function",
        "function": {
            "name": "generate_project_architecture",
            "description": "Сканирует весь проект, строит дерево каталогов, анализирует связи между модулями и генерирует файл project_architecture.md.",
            "parameters": {
                "type": "object", 
                "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_tasks",
            "description": "Управляет локальным таск-трекером спринтов. Позволяет создавать задачи ('create'), выводить список всех задач ('list') и закрывать их ('close').",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string", 
                        "description": "Действие с таск-трекером.", 
                        "enum": ["create", "list", "update_status", "close"]
                    },
                    "title": {"type": "string", "description": "Заголовок задачи (для 'create')."},
                    "description": {"type": "string", "description": "Описание задачи."},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "task_id": {"type": "integer", "description": "ID задачи для смены статуса."},
                    "status": {
                        "type": "string", 
                        "description": "Новый целевой статус.", 
                        "enum": ["backlog", "in_work", "testing", "done", "canceled"]
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_autotest_for_file",
            "description": "Автономно генерирует новые pytest-тесты для указанного Python-файла на основе его содержимого.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string", 
                        "description": "Относительный путь к файлу кода, для которого нужно написать тесты (например, 'functions/chat.py')."
                    }
                },
            "required": ["file_path"]
            }
        }
    }
]
