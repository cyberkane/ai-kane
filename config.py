import os

# Настройки сети Docker и Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434/v1/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "llama3.1:8b")

# Управление контекстом
MAX_HISTORY_LEN = 10  
NUM_CTX = 4096        

# Функция для динамического чтения системного промпта из внешнего файла
def load_system_prompt(filename="system_prompt.md") -> str:
    default_prompt = "Ты полезный ИИ-ассистент."
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"[Ошибка чтения системного промпта]: {e}")
            return default_prompt
    else:
        print(f"[Предупреждение]: Файл {filename} не найден. Используется базовый промпт.")
        return default_prompt

# Инициализируем переменную промпта при старте приложения
SYSTEM_PROMPT = load_system_prompt()