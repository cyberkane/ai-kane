import json
import os
from config import SYSTEM_PROMPT, MAX_HISTORY_LEN

class ContextManager:
    def __init__(self):
        # Инициализируем историю с системного промпта
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        
    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self._optimize_context()
        
    def _optimize_context(self):
        # Если сообщений в истории (не считая системного промпта) больше лимита
        if len(self.history) > MAX_HISTORY_LEN + 1:
            # Вырезаем старые сообщения, но ВСЕГДА оставляем системный промпт на индексе 0
            system_prompt_node = self.history[0]
            recent_messages = self.history[-MAX_HISTORY_LEN:]
            
            # Собираем чистый плоский массив для OpenAI/Ollama API
            self.history = [system_prompt_node] + recent_messages

    def get_context(self):
        return self.history

    def save_history_to_disk(self, filename="history_log.json"):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
            print(f"\n[AI-Kane]: История диалога успешно сохранена в {filename}")
        except Exception as e:
            print(f"\n[Ошибка сохранения истории]: {e}")