import json
import os
from datetime import datetime
from config import SYSTEM_PROMPT, MAX_HISTORY_LEN

class ContextManager:
    def __init__(self):
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        
    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self._optimize_context()
        
    def _optimize_context(self):
        if len(self.history) > MAX_HISTORY_LEN + 1:
            system_prompt_node = self.history[0]
            recent_messages = self.history[-MAX_HISTORY_LEN:]
            self.history = [system_prompt_node] + recent_messages

    def get_context(self):
        return self.history

    def save_history_to_disk(self):
        # Автоматически создаем папку logs внутри директории проекта на NVMe
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Формируем имя файла с текущей датой и временем
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = os.path.join(log_dir, f"session_{timestamp}.json")
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
            print(f"\n[AI-Kane]: Сессия успешно сохранена в файл: {filename}")
        except Exception as e:
            print(f"\n[Ошибка сохранения истории]: {e}")